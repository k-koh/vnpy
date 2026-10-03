from abc import abstractmethod

import pyqtgraph as pg      # type: ignore

from vnpy.trader.ui import QtCore, QtGui, QtWidgets
from vnpy.trader.object import BarData

from .base import BLACK_COLOR, UP_COLOR, DOWN_COLOR, YELLOW_COLOR, GREY_COLOR, ORANGE_COLOR, MAGENTA_COLOR, PEN_WIDTH, \
    BAR_WIDTH, IV_RANGE_WIDTH, WHITE_COLOR
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

        # Qt は「今 dirty になった帯」だけを exposedRect で渡してくることが
        # ある（カーソル線が動いた、ラベルを置き直した等）。キャッシュの絵は
        # ここで決めた範囲そのままなので、その帯をそのまま使うと、次に全面
        # 再描画が来るまで残りが消えたままになる。見えている範囲全体で作る。
        # クリップは Qt がやるので描き過ぎの害は無く、カーソルだけが動いた
        # ときは範囲が変わらないので再構築すら起きない。
        view_box = self.getViewBox()
        if view_box is not None:
            (view_left, view_right), _ = view_box.viewRange()
            min_ix = max(0, int(view_left))
            max_ix = min(len(self._bar_picutures), int(view_right) + 2)
        else:
            min_ix = int(rect.left())
            max_ix = min(int(rect.right()), len(self._bar_picutures))
        min_ix = min(min_ix, max_ix)

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

        self._base_line_pen: QtGui.QPen = pg.mkPen(
            color=YELLOW_COLOR,
            width=PEN_WIDTH
        )
        self._base_line_pen.setStyle(QtCore.Qt.DotLine)

        self._market_time_pen: QtGui.QPen = pg.mkPen(
            color=GREY_COLOR,
            width=PEN_WIDTH
        )
        self._market_time_pen.setStyle(QtCore.Qt.DashLine)

        # Vertical line at the start of each new (ISO) week: solid white, so it
        # reads against both the dark ground and the red/cyan candles (the grey
        # day/night dividers are dashed and dimmer, so the two never confuse).
        self._week_line_pen: QtGui.QPen = pg.mkPen(
            color=WHITE_COLOR,
            width=PEN_WIDTH
        )
        self._week_line_pen.setStyle(QtCore.Qt.SolidLine)

        # Pens for the candle shadow (ヒゲ). Same width as the body outline,
        # matching the エントリー判定 chart.
        self._up_wick_pen: QtGui.QPen = pg.mkPen(
            color=UP_COLOR, width=PEN_WIDTH
        )
        self._down_wick_pen: QtGui.QPen = pg.mkPen(
            color=DOWN_COLOR, width=PEN_WIDTH
        )

        # Reusable pool of σ-level labels (±0.5σ, ±1.0σ …) drawn at the right
        # edge next to the latest bar's ATM-IV band lines.
        self._sigma_labels: list[pg.TextItem] = []

        # 現在値が 0σ からいくつ離れているかのラベル。現在値の線の上に乗る。
        self._now_sigma_label: "pg.TextItem | None" = None

        # Last-price right-edge price tag (toggled from the toolbar; created
        # lazily once we have a ViewBox).
        self.show_last_price: bool = False
        self._last_price_label: "pg.TextItem | None" = None

        # Round-number (every 500) horizontal grid lines (toolbar toggle).
        self.show_round_lines: bool = False
        self.round_step: int = 500
        self._round_pen: QtGui.QPen = pg.mkPen(color=(90, 90, 90), width=1)
        self._round_pen.setStyle(QtCore.Qt.PenStyle.DotLine)
        self._round_pen.setCosmetic(True)

    def set_show_last_price(self, show: bool) -> None:
        """Show/hide the latest-close right-edge price tag."""
        self.show_last_price = show
        self.update()

    def set_show_round_lines(self, show: bool) -> None:
        """Show/hide the every-500 round-number horizontal lines."""
        self.show_round_lines = show
        self.update()

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

    def _get_drawn_iv_bounds(self, ix: int) -> tuple[float, float] | None:
        """
        Return (lower_price, upper_price) for the outermost IV-band lines actually
        drawn for bar at ix, or None when no IV bands are drawn.

        Mirrors the multiplier ladder in _draw_bar_picture: a 0.5x band is always
        drawn, and the next 0.5x step is drawn each time close_price breaks
        through the current step (up to 3.0x).
        """
        bar = self._manager.get_bar(ix)
        if not bar:
            return None
        daily_iv = self._get_atm_iv_daily(ix)
        if daily_iv <= 0:
            return None

        base_price = bar.pre_close if bar.pre_close > 0 else bar.open_price

        upper_mult: float = 0.5
        for mult in (0.5, 1.0, 1.5, 2.0, 2.5):
            if bar.close_price > base_price * (1 + daily_iv * mult):
                upper_mult = mult + 0.5
            else:
                break

        lower_mult: float = 0.5
        for mult in (0.5, 1.0, 1.5, 2.0, 2.5):
            if bar.close_price < base_price * (1 - daily_iv * mult):
                lower_mult = mult + 0.5
            else:
                break

        upper_price = base_price * (1 + daily_iv * upper_mult)
        lower_price = base_price * (1 - daily_iv * lower_mult)
        return lower_price, upper_price

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """"""
        # Create objects
        candle_picture: QtGui.QPicture = QtGui.QPicture()
        painter: QtGui.QPainter = QtGui.QPainter(candle_picture)

        # Draw vertical lines at market day open (08:45) and night open (17:00)
        # first, so the candle/reference lines render on top of them.
        bar_time = bar.datetime.strftime("%H:%M")
        prev_bar: BarData | None = self._manager.get_bar(ix - 1) if ix > 0 else None
        if prev_bar:
            prev_time = prev_bar.datetime.strftime("%H:%M")
            # First bar at or after 08:45
            if bar_time >= "08:45" and (prev_time < "08:45" or prev_bar.datetime.date() != bar.datetime.date()):
                painter.setPen(self._market_time_pen)
                painter.drawLine(
                    QtCore.QPointF(ix, -999999),
                    QtCore.QPointF(ix, 999999)
                )
            # First bar at or after 17:00
            if bar_time >= "17:00" and prev_time < "17:00":
                painter.setPen(self._market_time_pen)
                painter.drawLine(
                    QtCore.QPointF(ix, -999999),
                    QtCore.QPointF(ix, 999999)
                )
        elif ix == 0 and bar_time >= "08:45":
            # First bar in the dataset
            painter.setPen(self._market_time_pen)
            painter.drawLine(
                QtCore.QPointF(ix, -999999),
                QtCore.QPointF(ix, 999999)
            )

        # Draw a vertical line at the first bar of each new ISO week.
        if prev_bar:
            if bar.datetime.isocalendar()[:2] != prev_bar.datetime.isocalendar()[:2]:
                painter.setPen(self._week_line_pen)
                painter.drawLine(
                    QtCore.QPointF(ix, -999999),
                    QtCore.QPointF(ix, 999999)
                )

        # Set painter color. Same convention as the エントリー判定 chart:
        # 陽線 = filled UP_COLOR, 陰線 = hollow DOWN_COLOR outline.
        if bar.close_price >= bar.open_price:
            body_pen = self._up_pen
            wick_pen = self._up_wick_pen
            painter.setBrush(self._up_brush)
        else:
            body_pen = self._down_pen
            wick_pen = self._down_wick_pen
            painter.setBrush(self._black_brush)

        # Draw candle shadow (ヒゲ)
        if bar.high_price > bar.low_price:
            painter.setPen(wick_pen)
            painter.drawLine(
                QtCore.QPointF(ix, bar.high_price),
                QtCore.QPointF(ix, bar.low_price)
            )

        # Draw candle body with the normal-width pen
        painter.setPen(body_pen)
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
            # upper_price = base_price * (1 + daily_iv)
            # lower_price = base_price * (1 - daily_iv)
            #
            # painter.setPen(self._upper_line_pen)
            # painter.drawLine(
            #     QtCore.QPointF(ix - BAR_WIDTH, upper_price),
            #     QtCore.QPointF(ix + BAR_WIDTH, upper_price)
            # )
            #
            # painter.setPen(self._lower_line_pen)
            # painter.drawLine(
            #     QtCore.QPointF(ix - BAR_WIDTH, lower_price),
            #     QtCore.QPointF(ix + BAR_WIDTH, lower_price)
            # )
            #
            painter.setPen(self._base_line_pen)
            painter.drawLine(
                QtCore.QPointF(ix - IV_RANGE_WIDTH, base_price),
                QtCore.QPointF(ix + IV_RANGE_WIDTH, base_price)
            )

            upper_price = base_price * (1 + daily_iv * 0.5)
            lower_price = base_price * (1 - daily_iv * 0.5)

            painter.setPen(self._upper_line_pen)
            painter.drawLine(
                QtCore.QPointF(ix - IV_RANGE_WIDTH, upper_price),
                QtCore.QPointF(ix + IV_RANGE_WIDTH, upper_price)
            )

            painter.setPen(self._lower_line_pen)
            painter.drawLine(
                QtCore.QPointF(ix - BAR_WIDTH, lower_price),
                QtCore.QPointF(ix + BAR_WIDTH, lower_price)
            )

            if bar.close_price > upper_price:
                painter.setPen(self._upper_line_pen)
                upper_price = base_price * (1 + daily_iv)
                painter.drawLine(
                    QtCore.QPointF(ix - IV_RANGE_WIDTH, upper_price),
                    QtCore.QPointF(ix + IV_RANGE_WIDTH, upper_price)
                )
            elif bar.close_price < lower_price:
                painter.setPen(self._lower_line_pen)
                lower_price = base_price * (1 - daily_iv)
                painter.drawLine(
                    QtCore.QPointF(ix - IV_RANGE_WIDTH, lower_price),
                    QtCore.QPointF(ix + IV_RANGE_WIDTH, lower_price)
                )

            upper_price = base_price * (1 + daily_iv * 1.0)
            lower_price = base_price * (1 - daily_iv * 1.0)
            if bar.close_price > upper_price:
                painter.setPen(self._upper_line_pen)
                upper_price = base_price * (1 + daily_iv * 1.5)
                painter.drawLine(
                    QtCore.QPointF(ix - IV_RANGE_WIDTH, upper_price),
                    QtCore.QPointF(ix + IV_RANGE_WIDTH, upper_price)
                )
            elif bar.close_price < lower_price:
                painter.setPen(self._lower_line_pen)
                lower_price = base_price * (1 - daily_iv * 1.5)
                painter.drawLine(
                    QtCore.QPointF(ix - IV_RANGE_WIDTH, lower_price),
                    QtCore.QPointF(ix + IV_RANGE_WIDTH, lower_price)
                )

            upper_price = base_price * (1 + daily_iv * 1.5)
            lower_price = base_price * (1 - daily_iv * 1.5)
            if bar.close_price > upper_price:
                painter.setPen(self._upper_line_pen)
                upper_price = base_price * (1 + daily_iv * 2.0)
                painter.drawLine(
                    QtCore.QPointF(ix - IV_RANGE_WIDTH, upper_price),
                    QtCore.QPointF(ix + IV_RANGE_WIDTH, upper_price)
                )
            elif bar.close_price < lower_price:
                painter.setPen(self._lower_line_pen)
                lower_price = base_price * (1 - daily_iv * 2.0)
                painter.drawLine(
                    QtCore.QPointF(ix - IV_RANGE_WIDTH, lower_price),
                    QtCore.QPointF(ix + IV_RANGE_WIDTH, lower_price)
                )
            upper_price = base_price * (1 + daily_iv * 2.0)
            lower_price = base_price * (1 - daily_iv * 2.0)
            if bar.close_price > upper_price:
                painter.setPen(self._upper_line_pen)
                upper_price = base_price * (1 + daily_iv * 2.5)
                painter.drawLine(
                    QtCore.QPointF(ix - IV_RANGE_WIDTH, upper_price),
                    QtCore.QPointF(ix + IV_RANGE_WIDTH, upper_price)
                )
            elif bar.close_price < lower_price:
                painter.setPen(self._lower_line_pen)
                lower_price = base_price * (1 - daily_iv * 2.5)
                painter.drawLine(
                    QtCore.QPointF(ix - IV_RANGE_WIDTH, lower_price),
                    QtCore.QPointF(ix + IV_RANGE_WIDTH, lower_price)
                )

            upper_price = base_price * (1 + daily_iv * 2.5)
            lower_price = base_price * (1 - daily_iv * 2.5)
            if bar.close_price > upper_price:
                painter.setPen(self._upper_line_pen)
                upper_price = base_price * (1 + daily_iv * 3.0)
                painter.drawLine(
                    QtCore.QPointF(ix - IV_RANGE_WIDTH, upper_price),
                    QtCore.QPointF(ix + IV_RANGE_WIDTH, upper_price)
                )
            elif bar.close_price < lower_price:
                painter.setPen(self._lower_line_pen)
                lower_price = base_price * (1 - daily_iv * 3.0)
                painter.drawLine(
                    QtCore.QPointF(ix - IV_RANGE_WIDTH, lower_price),
                    QtCore.QPointF(ix + IV_RANGE_WIDTH, lower_price)
                )
        # Finish
        painter.end()
        return candle_picture

    def paint(self, painter: QtGui.QPainter, opt, w) -> None:  # type: ignore[override]
        """Paint the cached bar pictures, then overlay σ-level labels on the
        latest bar's ATM-IV band lines."""
        self._draw_round_lines(painter)     # behind the candles
        super().paint(painter, opt, w)
        self._update_sigma_labels()
        self._update_last_price(painter)

    def _draw_round_lines(self, painter: QtGui.QPainter) -> None:
        """Draw faint dark-grey horizontal lines at every round_step (500) yen
        across the visible range."""
        if not self.show_round_lines:
            return
        vb = self.getViewBox()
        if vb is None:
            return
        (x0v, x1v), (y0v, y1v) = vb.viewRange()
        if y1v <= y0v or x1v <= x0v:
            return
        step: int = self.round_step
        painter.setPen(self._round_pen)
        start: int = int((y0v // step + 1) * step) if y0v % step else int(y0v)
        y: float = float(start)
        while y <= y1v:
            painter.drawLine(QtCore.QPointF(x0v, y), QtCore.QPointF(x1v, y))
            y += step

    def _update_last_price(self, painter: QtGui.QPainter) -> None:
        """Draw a horizontal line at the latest close, with a price tag on the
        right axis (outside the plot) so it never covers the newest candles.

        Same look as the エントリー判定 chart: a solid line in the candle's
        colour across the whole view, and a filled tag of that colour with
        black text sitting where the y-axis ticks are.
        """
        vb = self.getViewBox()
        count: int = self._manager.get_count()
        bar = self._manager.get_bar(count - 1) if count else None
        if vb is None or bar is None or not self.show_last_price:
            if self._last_price_label is not None:
                self._last_price_label.hide()
            return

        price: float = bar.close_price
        color = UP_COLOR if bar.close_price >= bar.open_price else DOWN_COLOR

        # The tag is a child of the PlotItem, not of the ViewBox: the ViewBox
        # clips its children to the plot area, and we want the tag outside it.
        plot_item = vb.parentItem()
        if self._last_price_label is None:
            label = pg.TextItem(anchor=(0.0, 0.5), color=BLACK_COLOR)
            label.setFont(QtGui.QFont("Arial", 10))
            if plot_item is not None:
                label.setParentItem(plot_item)
            else:
                vb.addItem(label, ignoreBounds=True)
            self._last_price_label = label
        label = self._last_price_label

        (x0v, x1v), (y0v, y1v) = vb.viewRange()
        if not (y0v <= price <= y1v):
            label.hide()                      # 現在値が表示範囲の外
        else:
            label.setText(f"{price:,.0f}")
            label.fill = pg.mkBrush(color)    # 地色は足の色（塗りは paint 時に使われる）
            if plot_item is not None:
                scene_point = vb.mapViewToScene(QtCore.QPointF(x1v, price))
                local = plot_item.mapFromScene(scene_point)
                label.setPos(local.x() + 3, local.y())
            else:
                label.setPos(x1v, price)
            label.show()

        # 線は全幅の実線。タグは軸の外なので、途中で止める必要がない。
        if x1v <= x0v:
            return
        pen = pg.mkPen(color=color, width=1)
        pen.setCosmetic(True)                 # constant 1px width at any zoom
        painter.setPen(pen)
        painter.drawLine(
            QtCore.QPointF(x0v, price),
            QtCore.QPointF(x1v, price),
        )

    def _update_sigma_labels(self) -> None:
        """Place ±0.5σ/±1.0σ… labels next to the latest bar's drawn ATM-IV
        band lines. Only the bands actually drawn for the latest bar (base,
        ±0.5σ, and the one-sided ladder up to the close) get a label; when
        there are no band lines (no ATM IV) all labels are hidden."""
        vb = self.getViewBox()
        count: int = self._manager.get_count()
        if vb is None or count == 0:
            self._hide_sigma_labels()
            return

        last_ix: int = count - 1
        # The first bar after a session open (17:00) hasn't had its ATM IV
        # computed yet, so fall back to the most recent bar that has a valid
        # one — the labels still show, positioned at the latest bar.
        ref_ix: int = last_ix
        daily_iv: float = self._get_atm_iv_daily(ref_ix)
        if daily_iv <= 0:
            scan: int = last_ix - 1
            limit: int = max(0, last_ix - 500)
            while scan >= limit:
                div: float = self._get_atm_iv_daily(scan)
                if div > 0:
                    ref_ix, daily_iv = scan, div
                    break
                scan -= 1

        bar = self._manager.get_bar(ref_ix)
        if bar is None or daily_iv <= 0:
            self._hide_sigma_labels()
            return

        base: float = bar.pre_close if bar.pre_close > 0 else bar.open_price
        close: float = bar.close_price

        # (text, price, color) — mirror the ladder drawn in _draw_bar_picture:
        # base + ±0.5σ always, then higher levels only on the side the close
        # has broken through, up to the band just beyond the close.
        entries: list[tuple[str, float, tuple]] = [
            ("0σ", base, YELLOW_COLOR),
            ("+0.5σ", base * (1 + daily_iv * 0.5), UP_COLOR),
            ("-0.5σ", base * (1 - daily_iv * 0.5), DOWN_COLOR),
        ]
        for mult in (1.0, 1.5, 2.0, 2.5, 3.0):
            if close > base * (1 + daily_iv * (mult - 0.5)):
                entries.append((f"+{mult:.1f}σ", base * (1 + daily_iv * mult), UP_COLOR))
            else:
                break
        for mult in (1.0, 1.5, 2.0, 2.5, 3.0):
            if close < base * (1 - daily_iv * (mult - 0.5)):
                entries.append((f"-{mult:.1f}σ", base * (1 - daily_iv * mult), DOWN_COLOR))
            else:
                break

        while len(self._sigma_labels) < len(entries):
            lbl = pg.TextItem(anchor=(0.0, 0.5))
            # Explicit family: the default/empty-family font lacks the Greek
            # σ glyph and silently drops it (label showed "+0.5", not "+0.5σ").
            lbl.setFont(QtGui.QFont("Arial", 8))
            vb.addItem(lbl, ignoreBounds=True)
            self._sigma_labels.append(lbl)

        for i, lbl in enumerate(self._sigma_labels):
            if i >= len(entries):
                lbl.hide()
                continue
            text, price, color = entries[i]
            lbl.setColor(color)
            # Append the futures price at that σ level (like トレンドライン labels).
            lbl.setText(f"{text}  {price:,.0f}")
            lbl.setPos(last_ix + 0.6, price)
            lbl.show()

        self._update_now_sigma_label(vb, last_ix, base, daily_iv)

    def _hide_sigma_labels(self) -> None:
        """σのラベルを全部隠す（現在σも含む）。"""
        for lbl in self._sigma_labels:
            lbl.hide()
        if self._now_sigma_label is not None:
            self._now_sigma_label.hide()

    def _update_now_sigma_label(
        self, vb, last_ix: int, base: float, daily_iv: float
    ) -> None:
        """現在値が 0σ（前日の引け）から何σ離れているかを出す。

        はしごは0.5σ刻みの線しか無いので、その間にいるときに今どのあたりかが
        読めない。現在値の線のすぐ上に置き、開始位置は他のσラベルと揃える。
        """
        last_bar = self._manager.get_bar(last_ix)
        if last_bar is None or base <= 0 or daily_iv <= 0:
            if self._now_sigma_label is not None:
                self._now_sigma_label.hide()
            return

        close: float = last_bar.close_price
        sigma: float = (close - base) / (base * daily_iv)

        if self._now_sigma_label is None:
            # anchor (0.0, 1.0): 左下が基準 → 文字は現在値の線の「上」に出る。
            lbl = pg.TextItem(anchor=(0.0, 1.0))
            lbl.setFont(QtGui.QFont("Arial", 8))
            vb.addItem(lbl, ignoreBounds=True)
            self._now_sigma_label = lbl

        label = self._now_sigma_label
        label.setColor(UP_COLOR if sigma >= 0 else DOWN_COLOR)
        label.setText(f"{sigma:+.2f}σ")
        label.setPos(last_ix + 0.6, close)
        label.show()

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
            max_ix = len(bars) - 1

        if not (self._manager.get_count() and max_ix >= min_ix):
            return min_price, max_price

        for ix in range(min_ix, max_ix + 1):
            bounds = self._get_drawn_iv_bounds(ix)
            if bounds is None:
                continue
            lower_price, upper_price = bounds
            min_price = min(min_price, lower_price)
            max_price = max(max_price, upper_price)

        return min_price, max_price

    def get_info_text(self, ix: int) -> str:
        """
        Get information text to show by cursor.
        """
        bar: BarData | None = self._manager.get_bar(ix)

        if bar:
            close = f"{bar.close_price:.0f}"
            words: list = [
                bar.datetime.strftime("%Y-%m-%d"),
                bar.datetime.strftime("%H:%M"),
                close
            ]

            daily_iv = self._get_atm_iv_daily(ix)
            if daily_iv > 0:
                base_price = bar.pre_close if bar.pre_close > 0 else bar.open_price
                for mult in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
                    upper_price = base_price * (1 + daily_iv * mult)
                    lower_price = base_price * (1 - daily_iv * mult)
                    words.append(f"U{mult}: {upper_price:.0f} L{mult}: {lower_price:.0f}")
            # words: list = [
            #     "Date",
            #     bar.datetime.strftime("%Y-%m-%d"),
            #     "",
            #     "Time",
            #     bar.datetime.strftime("%H:%M"),
            #     "",
            #     "Open",
            #     str(bar.open_price),
            #     "",
            #     "High",
            #     str(bar.high_price),
            #     "",
            #     "Low",
            #     str(bar.low_price),
            #     "",
            #     "Close",
            #     str(bar.close_price)
            # ]
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
