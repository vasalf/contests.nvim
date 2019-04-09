import pynvim

@pynvim.plugin
class ContestsPlugin(object):
    def __init__(self, nvim):
        self.nvim = nvim
        self.launched = False
        self.input_buffer = None
        self.output_buffer = None
        self.main_window = None
        self.input_window = None
        self.output_window = None

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
        self.create_buffers(args)
        self.open_windows(args)
        self.resize_windows(args)
        self.launched = True

