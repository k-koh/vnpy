from abc import abstractmethod

import pyqtgraph as pg      # type: ignore

from vnpy.trader.ui import QtCore, QtGui, QtWidgets
from vnpy.trader.object import BarData

from .base import BLACK_COLOR, UP_COLOR, DOWN_COLOR, PEN_WIDTH, BAR_WIDTH
from .manager import BarManager


class ChartItem(pg.GraphicsObject):
    """"""

    def __init__(self, manager: BarManager) -> None:
        """"""
        super().__init__()

        self._manager: BarManager = manager

        self._bar_picutures: dict[int, QtGui.QPicture | None] = {}
        self._item_picuture: QtGui.QPicture | None = None

        self._black_brush: QtGui.QBrush = pg.mkBrush(color=BLACK_COLOR)

        self._up_pen: QtGui.QPen = pg.mkPen(
            color=UP_COLOR, width=PEN_WIDTH
        )
        self._up_brush: QtGui.QBrush = pg.mkBrush(color=UP_COLOR)

        self._down_pen: QtGui.QPen = pg.mkPen(
            color=DOWN_COLOR, width=PEN_WIDTH
        )
        self._down_brush: QtGui.QBrush = pg.mkBrush(color=DOWN_COLOR)

        self._rect_area: tuple[float, float] | None = None

        # Very important! Only redraw the visible part and improve speed a lot.
        self.setFlag(self.GraphicsItemFlag.ItemUsesExtendedStyleOption)

        # Force update during the next paint
        self._to_update: bool = False

    @abstractmethod
    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """
        Draw picture for specific bar.
        """
        pass

    @abstractmethod
    def boundingRect(self) -> QtCore.QRectF:
        """
        Get bounding rectangles for item.
        """
        pass

    @abstractmethod
    def get_y_range(self, min_ix: int | None = None, max_ix: int | None = None) -> tuple[float, float]:
        """
        Get range of y-axis with given x-axis range.

        If min_ix and max_ix not specified, then return range with whole data set.
        """
        pass

    @abstractmethod
    def get_info_text(self, ix: int) -> str:
        """
        Get information text to show by cursor.
        """
        pass

    def update_history(self, history: list[BarData]) -> None:
        """
        Update a list of bar data.
        """
        self._bar_picutures.clear()

        bars: list[BarData] = self._manager.get_all_bars()

        for ix, _ in enumerate(bars):
            self._bar_picutures[ix] = None

        self.update()

    def update_bar(self, bar: BarData) -> None:
        """
        Update single bar data.
        """
        ix: int | None = self._manager.get_index(bar.datetime)
        if ix is None:
            return

        self._bar_picutures[ix] = None

        self.update()

    def update(self) -> None:
        """
        Refresh the item.
        """
        if self.scene():
            self._to_update = True
            self.scene().update()

    def paint(
        self,
        painter: QtGui.QPainter,
        opt: QtWidgets.QStyleOptionGraphicsItem,
        w: QtWidgets.QWidget
    ) -> None:
        """
        Reimplement the paint method of parent class.

        This function is called by external QGraphicsView.
        """
        rect: QtCore.QRectF = opt.exposedRect       # type: ignore

        min_ix: int = int(rect.left())
        max_ix: int = int(rect.right())
        max_ix = min(max_ix, len(self._bar_picutures))

        rect_area: tuple = (min_ix, max_ix)
        if (
            self._to_update
            or rect_area != self._rect_area
            or not self._item_picuture
        ):
            self._to_update = False
            self._rect_area = rect_area
            self._draw_item_picture(min_ix, max_ix)

        if self._item_picuture:
            self._item_picuture.play(painter)

    def _draw_item_picture(self, min_ix: int, max_ix: int) -> None:
        """
        Draw the picture of item in specific range.
        """
        self._item_picuture = QtGui.QPicture()
        painter: QtGui.QPainter = QtGui.QPainter(self._item_picuture)

        for ix in range(min_ix, max_ix):
            bar_picture: QtGui.QPicture | None = self._bar_picutures[ix]

            if bar_picture is None:
                bar: BarData | None = self._manager.get_bar(ix)
                if bar is None:
                    continue

                bar_picture = self._draw_bar_picture(ix, bar)
                self._bar_picutures[ix] = bar_picture

            bar_picture.play(painter)

        painter.end()

    def clear_all(self) -> None:
        """
        Clear all data in the item.
        """
        self._item_picuture = None
        self._bar_picutures.clear()
        self.update()


class CandleItem(ChartItem):
    """"""

    def __init__(self, manager: BarManager) -> None:
        """"""
        super().__init__(manager)

        self._atm_iv_daily: dict[int, float] = {}

        self._upper_line_pen: QtGui.QPen = pg.mkPen(
            color=UP_COLOR,
            width=PEN_WIDTH
        )
        self._upper_line_pen.setStyle(QtCore.Qt.DashLine)

        self._lower_line_pen: QtGui.QPen = pg.mkPen(
            color=DOWN_COLOR,
            width=PEN_WIDTH
        )
        self._lower_line_pen.setStyle(QtCore.Qt.DashLine)

    def _get_atm_iv_daily(self, ix: int) -> float:
        """"""
        if ix in self._atm_iv_daily:
            return self._atm_iv_daily[ix]

        bar = self._manager.get_bar(ix)
        if bar and bar.atm_iv:
            daily_iv = bar.atm_iv / (252 ** 0.5)
        else:
            daily_iv = 0
        self._atm_iv_daily[ix] = daily_iv
        return daily_iv

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """"""
        # Create objects
        candle_picture: QtGui.QPicture = QtGui.QPicture()
        painter: QtGui.QPainter = QtGui.QPainter(candle_picture)

        # Set painter color
        if bar.close_price >= bar.open_price:
            painter.setPen(self._up_pen)
            painter.setBrush(self._black_brush)
        else:
            painter.setPen(self._down_pen)
            painter.setBrush(self._down_brush)

        # Draw candle shadow
        if bar.high_price > bar.low_price:
            painter.drawLine(
                QtCore.QPointF(ix, bar.high_price),
                QtCore.QPointF(ix, bar.low_price)
            )

        # Draw candle body
        if bar.open_price == bar.close_price:
            painter.drawLine(
                QtCore.QPointF(ix - BAR_WIDTH, bar.open_price),
                QtCore.QPointF(ix + BAR_WIDTH, bar.open_price),
            )
        else:
            rect: QtCore.QRectF = QtCore.QRectF(
                ix - BAR_WIDTH,
                bar.open_price,
                BAR_WIDTH * 2,
                bar.close_price - bar.open_price
            )
            painter.drawRect(rect)

        # Draw ATM IV daily lines
        daily_iv = self._get_atm_iv_daily(ix)
        if daily_iv > 0:
            base_price = bar.pre_close if bar.pre_close > 0 else bar.open_price
            upper_price = base_price * (1 + daily_iv)
            lower_price = base_price * (1 - daily_iv)

            painter.setPen(self._upper_line_pen)
            painter.drawLine(
                QtCore.QPointF(ix - BAR_WIDTH, upper_price),
                QtCore.QPointF(ix + BAR_WIDTH, upper_price)
            )

            painter.setPen(self._lower_line_pen)
            painter.drawLine(
                QtCore.QPointF(ix - BAR_WIDTH, lower_price),
                QtCore.QPointF(ix + BAR_WIDTH, lower_price)
            )

        # Finish
        painter.end()
        return candle_picture

    def boundingRect(self) -> QtCore.QRectF:
        """"""
        min_price, max_price = self._manager.get_price_range()
        rect: QtCore.QRectF = QtCore.QRectF(
            0,
            min_price,
            len(self._bar_picutures),
            max_price - min_price
        )
        return rect

    def get_y_range(self, min_ix: int | None = None, max_ix: int | None = None) -> tuple[float, float]:
        """
        Get range of y-axis with given x-axis range.

        If min_ix and max_ix not specified, then return range with whole data set.
        """
        min_price, max_price = self._manager.get_price_range(min_ix, max_ix)
        
        if min_ix is None or max_ix is None:
            bars = self._manager.get_all_bars()
            min_ix = 0
            max_ix = len(bars) -1

        if not (self._manager.get_count() and max_ix >= min_ix):
            return min_price, max_price

        for ix in range(min_ix, max_ix + 1):
            bar = self._manager.get_bar(ix)
            if not bar:
                continue

            daily_iv = self._get_atm_iv_daily(ix)
            if daily_iv > 0:
                base_price = bar.pre_close if bar.pre_close > 0 else bar.open_price
                upper_price = base_price * (1 + daily_iv)
                lower_price = base_price * (1 - daily_iv)
                min_price = min(min_price, lower_price)
                max_price = max(max_price, upper_price)

        return min_price, max_price

    def get_info_text(self, ix: int) -> str:
        """
        Get information text to show by cursor.
        """
        bar: BarData | None = self._manager.get_bar(ix)

        if bar:
            words: list = [
                "Date",
                bar.datetime.strftime("%Y-%m-%d"),
                "",
                "Time",
                bar.datetime.strftime("%H:%M"),
                "",
                "Open",
                str(bar.open_price),
                "",
                "High",
                str(bar.high_price),
                "",
                "Low",
                str(bar.low_price),
                "",
                "Close",
                str(bar.close_price)
            ]
            text: str = "\n".join(words)
        else:
            text = ""

        return text

    def clear_all(self) -> None:
        """
        Clear all data in the item.
        """
        self._atm_iv_daily.clear()
        super().clear_all()


class VolumeItem(ChartItem):
    """"""

    def __init__(self, manager: BarManager) -> None:
        """"""
        super().__init__(manager)

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """"""
        # Create objects
        volume_picture: QtGui.QPicture = QtGui.QPicture()
        painter: QtGui.QPainter = QtGui.QPainter(volume_picture)

        # Set painter color
        if bar.close_price >= bar.open_price:
            painter.setPen(self._up_pen)
            painter.setBrush(self._up_brush)
        else:
            painter.setPen(self._down_pen)
            painter.setBrush(self._down_brush)

        # Draw volume body
        rect: QtCore.QRectF = QtCore.QRectF(
            ix - BAR_WIDTH,
            0,
            BAR_WIDTH * 2,
            bar.volume
        )
        painter.drawRect(rect)

        # Finish
        painter.end()
        return volume_picture

    def boundingRect(self) -> QtCore.QRectF:
        """"""
        min_volume, max_volume = self._manager.get_volume_range()
        rect: QtCore.QRectF = QtCore.QRectF(
            0,
            min_volume,
            len(self._bar_picutures),
            max_volume - min_volume
        )
        return rect

    def get_y_range(self, min_ix: int | None = None, max_ix: int | None = None) -> tuple[float, float]:
        """
        Get range of y-axis with given x-axis range.

        If min_ix and max_ix not specified, then return range with whole data set.
        """
        min_volume, max_volume = self._manager.get_volume_range(min_ix, max_ix)
        return min_volume, max_volume

    def get_info_text(self, ix: int) -> str:
        """
        Get information text to show by cursor.
        """
        bar: BarData | None = self._manager.get_bar(ix)

        if bar:
            text: str = f"Volume {bar.volume}"
        else:
            text = ""

        return text
