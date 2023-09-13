class Frame:
    WIDTH = 256
    HEIGHT = 240

    def __init__(self) -> None:
        self.data = [(0,0,0)] * Frame.WIDTH * Frame.HEIGHT

    def set_pixel(self, x: int, y: int, rgb: list[int]):
        position = y * Frame.WIDTH + x
        if position < 256 * 240:
            self.data[position] = rgb
