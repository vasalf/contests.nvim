import abc
import pynvim
import subprocess
import sys


class Launcher(abc.ABC):
    def launch(self, cmd, stdin):
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   encoding="UTF8")
        process.stdin.write(stdin)
        process.stdin.flush()
        process.stdin.close()
        process.wait()

        stdout = process.stdout.read()
        stderr = process.stderr.read()
        if stdout == "":
            return stderr, process.returncode
        if stderr == "":
            return stdout, process.returncode
        if stdout[-1] != "\n":
            stdout += "\n"
        return stdout + stderr, process.returncode

    @abc.abstractmethod
    def compile(self):
        pass

    @abc.abstractmethod
    def run(self, stdin):
        pass


class PythonLauncher(Launcher):
    def __init__(self, filename):
        self.filename = filename

    def compile(self):
        return True

    def run(self, stdin):
        return self.launch(["python3", self.filename], stdin)


class CppLauncher(Launcher):
    def __init__(self, nvim, filename):
        self.nvim = nvim
        self.filename = filename
        self.executable = self.filename[:self.filename.rfind('.')]

    def compile(self):
        out, ret = self.launch(["g++", "-std=c++17",
                               "-Wall", "-Wextra","-Wshadow",
                               "-fsanitize=undefined", "-DLOCAL", "-D_GLIBCXX_DEBUG", "-ggdb3",
                               self.filename, "-o", self.executable], "")
        if out != "":
            self.nvim.command(f'echo "{out}"')
        return ret == 0

    def run(self, stdin):
        return self.launch([self.executable], stdin)


@pynvim.plugin
class ContestsPlugin(object):
    def __init__(self, nvim):
        self.nvim = nvim
        self.launched = False
        self.launching = False
        self.launcher = None
        self.main_buffer = None
        self.input_buffer = None
        self.output_buffer = None
        self.main_window = None
        self.input_window = None
        self.output_window = None

    def __select_launcher(self, filename):
        if filename.endswith(".py"):
            return PythonLauncher(filename)
        if filename.endswith(".cpp"):
            return CppLauncher(self.nvim, filename)
        return None

    def __split_window(self, vertical=False):
        ret = self.nvim.api.get_current_win()
        old_wins = set(self.nvim.api.list_wins())
        self.nvim.funcs.execute(":vs" if vertical else ":sp")
        for win in self.nvim.api.list_wins():
            if win not in old_wins:
                return (win, ret)

    @pynvim.function("ContestsHelloPython", sync=True)
    def ContestsHelloPython(self, args):
        self.nvim.command('echo "Hello!"')

    @pynvim.function("ContestsCreateBuffers")
    def create_buffers(self, args):
        self.main_buffer = self.nvim.api.get_current_buf()
        self.input_buffer = self.nvim.api.create_buf(True, True)
        self.nvim.api.buf_set_name(self.input_buffer, "[olymp-input]")
        self.output_buffer = self.nvim.api.create_buf(True, True)
        self.nvim.api.buf_set_name(self.output_buffer, "[olymp-output]")

    @pynvim.function("ContestsOpenWindows")
    def open_windows(self, args):
        ## Input window
        (mw, iw) = self.__split_window(vertical=True)
        self.nvim.api.set_current_win(iw)
        self.nvim.api.set_current_buf(self.input_buffer)
        ## Output window
        (iw, ow) = self.__split_window()
        self.nvim.api.set_current_win(ow)
        self.nvim.api.set_current_buf(self.output_buffer)
        self.nvim.api.set_current_win(mw)
        ## Set windows
        self.main_window = mw
        self.input_window = iw
        self.output_window = ow

    @pynvim.function("ContestsResizeWindows")
    def resize_windows(self, args):
        height = self.main_window.height
        width = self.main_window.width + self.input_window.width
        io_buf_width = width // 3
        self.nvim.api.win_set_height(self.input_window, (height + 1) // 2)
        self.nvim.api.win_set_width(self.output_window, height // 2)
        self.nvim.api.win_set_width(self.main_window, width - io_buf_width)

    @pynvim.autocmd("VimResized")
    def au_resize_windows(self):
        if self.launched:
            self.resize_windows([])

    @pynvim.function("ContestsInit")
    def init(self, args):
        if self.launched or self.launching:
            return
        launcher = self.__select_launcher(self.nvim.api.buf_get_name(self.nvim.api.get_current_buf()))
        if launcher is None:
            return
        self.launching = True
        self.create_buffers(args)
        self.open_windows(args)
        self.resize_windows(args)
        self.launcher = launcher
        self.launching = False
        self.launched = True

    def __buf_contains(self, buf):
        line_count = self.nvim.api.buf_line_count(buf)
        lines = self.nvim.api.buf_get_lines(buf, 0, line_count, True)
        return "\n".join(lines)

    def __set_buf_text(self, buf, text):
        line_count = self.nvim.api.buf_line_count(buf)
        lines = text.split("\n")
        self.nvim.api.buf_set_lines(buf, 0, line_count, True, lines)

    def __run_tests(self):
        SPLITTER = "→ ###"
        line_count = self.nvim.api.buf_line_count(self.input_buffer)
        lines = self.nvim.api.buf_get_lines(self.input_buffer, 0, line_count, True)
        lines.append(SPLITTER)
        stdin = ""
        output = ""
        ci = 0
        for line in lines:
            if line == SPLITTER:
                cout, ret = self.launcher.run(stdin)
                if cout == "" or cout[-1] != "\n":
                    cout += "\n"
                if ret != 0:
                    cout += f"Command finished with exit code {ret}\n"
                output += cout
                if ci != len(lines) - 1:
                    output += SPLITTER + "\n"
                stdin = ""
            else:
                stdin += line + "\n"
            ci += 1
        self.__set_buf_text(self.output_buffer, output)

    @pynvim.function("ContestsRun")
    def run(self, args):
        if self.launched:
            if not self.launcher.compile():
                return
            self.__run_tests()

    @pynvim.function("ContestsCompile")
    def compile(self, args):
        if self.launched:
            self.launcher.compile()
