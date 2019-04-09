import abc
import pynvim
import subprocess
import sys


class Launcher(abc.ABC):
    def launch(self, cmd, stdin):
        result = subprocess.run(cmd,
                input=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="UTF8")
        stdout = result.stdout
        stderr = result.stderr
        if stdout == "":
            return stderr, result.returncode
        if stderr == "":
            return stdout, result.returncode
        if stdout[-1] != "\n":
            stdout += "\n"
        return stdout + stderr, result.returncode

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

    @pynvim.function("ContestsRun")
    def run(self, args):
        if self.launched:
            if not self.launcher.compile():
                return
            output, ret = self.launcher.run(self.__buf_contains(self.input_buffer))
            if ret != 0:
                output += f"Command finished with exit code {ret}"
            self.__set_buf_text(self.output_buffer, output)

    @pynvim.function("ContestsCompile")
    def compile(self, args):
        if self.launched:
            self.launcher.compile()
