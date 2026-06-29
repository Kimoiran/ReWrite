"""地图模块 — 所有坐标统一为绝对场景坐标，不存在任何相对偏移。"""

import json, uuid, math
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List

from PySide6.QtCore import Qt, QRectF, QPointF, QLineF
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QPolygonF,
                            QCursor, QPainterPath)
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsPolygonItem, QGraphicsPathItem, QGraphicsItem,
    QInputDialog, QMessageBox, QFormLayout,
    QLineEdit, QTextEdit, QComboBox, QDialogButtonBox, QDialog,
    QMenu, QGraphicsSimpleTextItem,
)
from .base_module import BaseModule


@dataclass
class MapNode:
    id: str = ""
    name: str = ""
    node_type: str = "city"
    x: float = 500.0
    y: float = 500.0
    parent_id: str = ""
    children: list = field(default_factory=list)
    description: str = ""
    tags: list = field(default_factory=list)
    color: str = ""
    radius: float = 0.0
    font_size: float = 0.0
    font_italic: bool = False
    boundary: list = field(default_factory=list)  # 绝对场景坐标


@dataclass
class MapRoute:
    id: str = ""
    name: str = ""
    color: str = "#e91e63"
    waypoints: list = field(default_factory=list)
    description: str = ""


NODE_TYPE_CONFIG = {
    "country":  {"label": "国家", "size": 14, "color": "#5C6BC0"},
    "region":   {"label": "地区", "size": 11, "color": "#66BB6A"},
    "city":     {"label": "城市", "size": 9,  "color": "#FFA726"},
    "district": {"label": "街区", "size": 6,  "color": "#AB47BC"},
    "poi":      {"label": "地标", "size": 4,  "color": "#EF5350"},
}

SNAP_DIST = 20

# --------------------------------------------------
#  Graphics Items — 绝对坐标体系
# --------------------------------------------------

_REBUILD = False  # 全局重建锁


class BoundaryVertex(QGraphicsEllipseItem):
    VERTEX_RADIUS = 5

    def __init__(self, idx: int, x: float, y: float, parent_poly=None):
        r = BoundaryVertex.VERTEX_RADIUS
        super().__init__(-r, -r, r * 2, r * 2, parent_poly)
        self._idx = idx
        self._skip = False
        self._last_pos = None
        self.setPos(x, y)
        self.setVisible(r > 0)
        self.setBrush(QBrush(QColor("#ffffff")))
        self.setPen(QPen(QColor("#333"), 1.5))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(10)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def itemChange(self, change, value):
        global _REBUILD
        if _REBUILD:
            return super().itemChange(change, value)
        p = self.parentItem()
        if not isinstance(p, BoundaryPolygon):
            return super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if self._last_pos is None:
                self._last_pos = self.pos()
            if self._skip:
                return super().itemChange(change, value)
            p._on_vertex_moved(self._idx, self.pos())
            return super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._skip:
                self._last_pos = self.pos()
                return super().itemChange(change, value)
            if not self.isSelected():
                self._last_pos = self.pos()
                return super().itemChange(change, value)
            dx = round(self.pos().x() - self._last_pos.x(), 1)
            dy = round(self.pos().y() - self._last_pos.y(), 1)
            self._last_pos = self.pos()
            if abs(dx) <= 0.5 and abs(dy) <= 0.5:
                return super().itemChange(change, value)
            has_sib = False
            for c in p.childItems():
                if isinstance(c, BoundaryVertex) and c != self and c.isSelected():
                    has_sib = True
                    c._skip = True
                    c.setPos(round(c.pos().x() + dx, 1), round(c.pos().y() + dy, 1))
                    c._skip = False
                    c._last_pos = c.pos()
            if has_sib:
                pts = p._collect_pts()
                if len(pts) >= 3:
                    p.setPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
                if p._on_dirty:
                    p._on_dirty(p._node_id, pts)
            return super().itemChange(change, value)
        return super().itemChange(change, value)


class BoundaryPolygon(QGraphicsPolygonItem):
    def __init__(self, node_id: str, vertices: list, color: QColor,
                 on_dirty=None, parent=None):
        super().__init__(parent)
        self._node_id = node_id
        self._on_dirty = on_dirty
        self._color = QColor(color)
        self.setPos(0, 0)
        self._build(vertices)
        self.setZValue(2)

    def _build(self, vertices):
        for c in self.childItems():
            if isinstance(c, BoundaryVertex):
                if self.scene(): self.scene().removeItem(c)
        if len(vertices) >= 3:
            poly = QPolygonF([QPointF(x, y) for x, y in vertices])
            self.setPolygon(poly)
            c = self._color
            self.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), 40)))
            self.setPen(QPen(QColor(c.red(), c.green(), c.blue(), 180), 1.5, Qt.PenStyle.DashLine))
        else:
            self.setPolygon(QPolygonF())
        for i, (x, y) in enumerate(vertices):
            BoundaryVertex(i, x, y, self)

    def _on_vertex_moved(self, idx, pos):
        pts = self._collect_pts()
        if len(pts) >= 3:
            self.setPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
        if self._on_dirty:
            self._on_dirty(self._node_id, pts)

    def _collect_pts(self):
        children = [c for c in self.childItems() if isinstance(c, BoundaryVertex)]
        children.sort(key=lambda c: c._idx)
        return [(round(c.pos().x(), 1), round(c.pos().y(), 1)) for c in children]


class RoutePathItem(QGraphicsPathItem):
    def __init__(self, route_id: str, waypoints: list, color: QColor,
                 name="", description="", on_dirty=None, parent=None):
        super().__init__(parent)
        self._route_id = route_id
        self._name = name
        self._description = description
        self._on_dirty = on_dirty
        self._color = QColor(color)
        self._waypoints = waypoints[:]
        self.setPos(0, 0)
        self._build()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setZValue(5)
        self.setToolTip(f"🚩 {name}" + (f"\n{description[:200]}" if description else ""))

    def _build(self):
        if len(self._waypoints) >= 2:
            path = QPainterPath()
            path.moveTo(self._waypoints[0][0], self._waypoints[0][1])
            for x, y in self._waypoints[1:]:
                path.lineTo(x, y)
            self.setPath(path)
        self.setPen(QPen(self._color, 3))
        self.setBrush(QBrush())

    def itemChange(self, change, value):
        global _REBUILD
        if _REBUILD:
            return super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if self._on_dirty:
                dx = round(value.x() - self.pos().x(), 1)
                dy = round(value.y() - self.pos().y(), 1)
                if abs(dx) > 0.5 or abs(dy) > 0.5:
                    self._waypoints = [[round(x + dx, 1), round(y + dy, 1)]
                                       for x, y in self._waypoints]
                    self._build()
                    self._on_dirty(self._route_id, self._waypoints)
        return super().itemChange(change, value)


class MapNodeItem(QGraphicsEllipseItem):
    NODE_RADIUS = 0

    def __init__(self, node_data: dict, on_move=None, parent=None):
        super().__init__(parent)
        self.node_data = node_data
        self._on_move = on_move
        self._label = QGraphicsSimpleTextItem(node_data.get("name", ""), self)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(11)
        self._sync()

    def _sync(self):
        cfg = NODE_TYPE_CONFIG.get(self.node_data.get("node_type", "city"), NODE_TYPE_CONFIG["city"])
        base_r = self.node_data.get("radius") or cfg["size"]
        r = MapNodeItem.NODE_RADIUS if MapNodeItem.NODE_RADIUS > 0 else base_r
        self.setRect(-r, -r, r * 2, r * 2)
        color = QColor(self.node_data.get("color") or cfg["color"])
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor(color).darker(120), 1))
        fs = self.node_data.get("font_size") or (9 if cfg["size"] >= 10 else 7)
        italic = self.node_data.get("font_italic", False)
        f = QFont(); f.setPointSize(int(fs)); f.setItalic(italic)
        self._label.setFont(f)
        self._label.setPos(r + 4, -max(r / 2, 4))
        self._label.setBrush(QBrush(QColor("#1a1a1a")))
        self._label.setText(self.node_data.get("name", ""))

    def itemChange(self, change, value):
        global _REBUILD
        if _REBUILD:
            return super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            ox = self.node_data.get("x", 0)
            oy = self.node_data.get("y", 0)
            self.node_data["x"] = round(value.x(), 1)
            self.node_data["y"] = round(value.y(), 1)
            if self._on_move:
                self._on_move(self.node_data.get("_id", ""),
                              self.node_data["x"] - ox,
                              self.node_data["y"] - oy)
        return super().itemChange(change, value)


# --------------------------------------------------
#  MapScene / MapView
# --------------------------------------------------

class MapScene(QGraphicsScene):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.clearSelection()
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            items = self.items(event.scenePos())
            if items and isinstance(items[0], BoundaryVertex):
                items[0].setSelected(not items[0].isSelected())
                event.accept()
                return
        super().mousePressEvent(event)


class MapView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scene.setSceneRect(-5000, -5000, 12000, 12000)
        self._zoom = 1.0
        self._draw_boundary = False
        self._draw_route = False
        self._draw_node_id = ""
        self._draw_pts = []
        self._draw_items = []
        self._boundary_done = None
        self._route_done = None
        self._node_ctx = None
        self._boundary_ctx = None
        self._route_ctx = None
        self._node_positions = {}

    def set_node_positions(self, nodes):
        self._node_positions = {n.id: (n.x, n.y) for n in nodes}

    def _find_snap_node(self, sx, sy):
        best, best_d = None, SNAP_DIST
        for nid, (nx, ny) in self._node_positions.items():
            d = math.hypot(sx - nx, sy - ny)
            if d < best_d:
                best_d = d
                best = (round(nx, 1), round(ny, 1), nid)
        return best

    def start_draw_boundary(self, node_id):
        self._draw_boundary = True
        self._draw_route = False
        self._draw_node_id = node_id
        self._clear_draw()
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def start_draw_route(self):
        self._draw_boundary = False
        self._draw_route = True
        self._draw_node_id = ""
        self._clear_draw()
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def end_draw(self):
        self._draw_boundary = False
        self._draw_route = False
        self._clear_draw()
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _clear_draw(self):
        s = self.scene()
        for it in self._draw_items:
            if s: s.removeItem(it)
        self._draw_items = []
        self._draw_pts = []

    def _add_dot(self, x, y, color="#e91e63", r=3):
        s = self.scene()
        dot = s.addEllipse(-r, -r, r * 2, r * 2, QPen(QColor(color), 2), QBrush(QColor(color)))
        dot.setPos(x, y); dot.setZValue(20)
        self._draw_items.append(dot)
        return dot

    def _add_line(self, x1, y1, x2, y2, color="#e91e63"):
        s = self.scene()
        line = s.addLine(QLineF(x1, y1, x2, y2), QPen(QColor(color), 2))
        line.setZValue(20); self._draw_items.append(line)

    def mousePressEvent(self, event):
        if self._draw_boundary and event.button() == Qt.MouseButton.LeftButton:
            sp = self.mapToScene(event.pos()); x, y = sp.x(), sp.y()
            if len(self._draw_pts) >= 3:
                first = self._draw_pts[0]
                if math.hypot(x - first[0], y - first[1]) < SNAP_DIST:
                    self._finish_boundary(); return
            self._draw_pts.append((x, y))
            if len(self._draw_pts) == 1:
                self._draw_first_dot = self._add_dot(x, y, "#e91e63", 5)
            else:
                prev = self._draw_pts[-2]
                self._add_line(prev[0], prev[1], x, y)
            self._add_dot(x, y)
            return
        if self._draw_boundary and event.button() == Qt.MouseButton.RightButton:
            if len(self._draw_pts) >= 3: self._finish_boundary()
            else: self._clear_draw()
            return
        if self._draw_route and event.button() == Qt.MouseButton.LeftButton:
            sp = self.mapToScene(event.pos())
            sn = self._find_snap_node(sp.x(), sp.y())
            x, y = sn[:2] if sn else (round(sp.x(), 1), round(sp.y(), 1))
            self._draw_pts.append((x, y))
            if len(self._draw_pts) >= 2:
                prev = self._draw_pts[-2]
                self._add_line(prev[0], prev[1], x, y)
            self._add_dot(x, y)
            return
        if self._draw_route and event.button() == Qt.MouseButton.RightButton:
            if len(self._draw_pts) >= 2: self._finish_route()
            else: self._clear_draw()
            return
        super().mousePressEvent(event)

    def _finish_boundary(self):
        pts = self._draw_pts[:]
        if len(pts) >= 3:
            first = pts[0]; last = pts[-1]
            if math.hypot(last[0] - first[0], last[1] - first[1]) > 2:
                self._add_line(last[0], last[1], first[0], first[1])
        self._clear_draw()
        if self._boundary_done: self._boundary_done(self._draw_node_id, pts)
        self.end_draw()

    def _finish_route(self):
        pts = self._draw_pts[:]
        self._clear_draw()
        if self._route_done: self._route_done(pts)
        self.end_draw()

    def contextMenuEvent(self, event):
        sp = self.mapToScene(event.pos())
        item = self.scene().itemAt(sp, self.transform())
        ctx = item
        while ctx and not isinstance(ctx, (BoundaryVertex, BoundaryPolygon, MapNodeItem, RoutePathItem)):
            ctx = ctx.parentItem()
        if isinstance(ctx, BoundaryVertex) and self._boundary_ctx: self._boundary_ctx(ctx)
        elif isinstance(ctx, BoundaryPolygon) and self._boundary_ctx: self._boundary_ctx(ctx)
        elif isinstance(ctx, RoutePathItem) and self._route_ctx: self._route_ctx(ctx)
        elif isinstance(ctx, MapNodeItem) and self._node_ctx: self._node_ctx(ctx)
        else: super().contextMenuEvent(event)

    def wheelEvent(self, event):
        f = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom = max(0.3, min(self._zoom * f, 10.0))
        self.scale(f, f)

    def fit_all(self):
        rect = self.scene().itemsBoundingRect().adjusted(-60, -60, 60, 60)
        if rect.width() < 10 or rect.height() < 10:
            rect = QRectF(0, 0, 1000, 1000)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 1.0


# --------------------------------------------------
#  Dialogs
# --------------------------------------------------

class MapNodeDialog(QDialog):
    def __init__(self, node: Optional[MapNode] = None, parent=None):
        super().__init__(parent)
        self._node = node
        self.setWindowTitle("编辑节点" if node else "添加节点")
        self.setMinimumWidth(350)
        lo = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("名称")
        if self._node: self.name_edit.setText(self._node.name)
        lo.addRow("名称:", self.name_edit)
        self.type_combo = QComboBox()
        for k, v in NODE_TYPE_CONFIG.items():
            self.type_combo.addItem(v["label"], k)
        if self._node:
            idx = self.type_combo.findData(self._node.node_type)
            if idx >= 0: self.type_combo.setCurrentIndex(idx)
        lo.addRow("类型:", self.type_combo)
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        if self._node: self.desc_edit.setPlainText(self._node.description)
        lo.addRow("描述:", self.desc_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        lo.addRow(btns)

    def get_data(self):
        return {"name": self.name_edit.text().strip(),
                "node_type": self.type_combo.currentData(),
                "description": self.desc_edit.toPlainText().strip()}


class MapRouteDialog(QDialog):
    def __init__(self, route_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑路线")
        self.setMinimumWidth(350)
        lo = QFormLayout(self)
        self.name_edit = QLineEdit(route_name)
        self.name_edit.setPlaceholderText("路线名称")
        lo.addRow("名称:", self.name_edit)
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(60)
        lo.addRow("描述:", self.desc_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        lo.addRow(btns)

    def get_data(self):
        return {"name": self.name_edit.text().strip(),
                "description": self.desc_edit.toPlainText().strip()}


# --------------------------------------------------
#  Module
# --------------------------------------------------

class MapModule(BaseModule):
    module_id = "map"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.data_path = work_path / "map.json"
        self.nodes: List[MapNode] = []
        self.routes: List[MapRoute] = []

    def load(self):
        if not self.data_path.exists():
            return
        try:
            data = json.loads(self.data_path.read_text(encoding="utf-8"))
            self.nodes = [MapNode(**n) for n in data.get("nodes", [])]
            # 迁移：检测相对偏移格式→转为绝对坐标
            migrated = False
            for n in self.nodes:
                if n.boundary and len(n.boundary) >= 3:
                    bx_vals = [b[0] for b in n.boundary]
                    by_vals = [b[1] for b in n.boundary]
                    max_dist = max(max(abs(x) for x in bx_vals), max(abs(y) for y in by_vals))
                    # 如果边界坐标接近原点（max < 300），说明是相对偏移→加节点位置
                    if max_dist < 300:
                        n.boundary = [[round(x + n.x, 1), round(y + n.y, 1)]
                                      for x, y in n.boundary]
                        migrated = True
            # 旧路线格式迁移
            raw_routes = data.get("routes", [])
            self.routes = []
            for r in raw_routes:
                if "nodes" in r and "waypoints" not in r:
                    wp = []
                    for nid in r.get("nodes", []):
                        nn = next((x for x in self.nodes if x.id == nid), None)
                        if nn: wp.append([nn.x, nn.y])
                    if not wp: wp = [[500, 500]]
                    r["waypoints"] = wp
                self.routes.append(MapRoute(**{k: v for k, v in r.items()
                                               if k in ("id","name","color","waypoints","description")}))
            if migrated:
                self.save()
        except Exception as e:
            print(f"加载地图失败: {e}")
            self.nodes = []; self.routes = []

    def save(self):
        try:
            self.data_path.write_text(
                json.dumps({"nodes": [asdict(n) for n in self.nodes],
                            "routes": [asdict(r) for r in self.routes]},
                           ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            print(f"保存地图失败: {e}")

    def add_node(self, name, node_type="city", x=500.0, y=500.0,
                 parent_id="", description="", boundary=None):
        n = MapNode(id=uuid.uuid4().hex[:12], name=name, node_type=node_type,
                    x=x, y=y, parent_id=parent_id, description=description,
                    boundary=boundary or [])
        self.nodes.append(n); return n

    def delete_node(self, nid):
        tod = set()
        def _c(i):
            tod.add(i)
            for n in self.nodes:
                if n.parent_id == i: _c(n.id)
        _c(nid)
        old = len(self.nodes)
        self.nodes = [n for n in self.nodes if n.id not in tod]
        for r in self.routes:
            r.waypoints = [wp for wp in r.waypoints]
        return len(self.nodes) < old

    def update_node(self, nid, **kw):
        for n in self.nodes:
            if n.id == nid:
                for k, v in kw.items():
                    if hasattr(n, k) and v is not None: setattr(n, k, v)
                return True
        return False

    def find_node_id(self, name):
        for n in self.nodes:
            if n.name == name: return n.id
        return None

    def add_route(self, name, waypoints, color="#e91e63", description=""):
        r = MapRoute(id=uuid.uuid4().hex[:12], name=name,
                     waypoints=waypoints, color=color, description=description)
        self.routes.append(r); return r

    def delete_route(self, rid):
        old = len(self.routes)
        self.routes = [r for r in self.routes if r.id != rid]
        return len(self.routes) < old

    def update_route(self, rid, **kw):
        for r in self.routes:
            if r.id == rid:
                for k, v in kw.items():
                    if hasattr(r, k) and v is not None: setattr(r, k, v)
                return True
        return False

    def search(self, q):
        q = q.lower()
        r = []
        for n in self.nodes:
            if q in n.name.lower() or q in n.description.lower():
                r.append((n.name, "map", n.id))
        for rt in self.routes:
            if q in rt.name.lower():
                r.append((rt.name, "route", rt.id))
        return r

    def create_dock_widget(self):
        return MapDock(self, None)


# --------------------------------------------------
#  Dock
# --------------------------------------------------

class MapDock(QDockWidget):
    def __init__(self, module: MapModule, parent=None):
        super().__init__("map", parent)
        self.module = module
        self._setup_ui()
        self._build_map()
        self._fit_view()
        self.setWindowTitle("map")

    def _setup_ui(self):
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea |
                             Qt.DockWidgetArea.RightDockWidgetArea |
                             Qt.DockWidgetArea.TopDockWidgetArea |
                             Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable |
                         QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.setMinimumSize(320, 240)
        w = QWidget(); lo = QVBoxLayout(w)
        lo.setContentsMargins(4, 4, 4, 4); lo.setSpacing(4)
        tb = QHBoxLayout()
        for t, fn in [("+", lambda: self._zoom_view(1.25)),
                      ("-", lambda: self._zoom_view(0.8)),
                      ("fit", self._fit_view)]:
            b = QPushButton(t); b.setFixedSize(28, 28)
            b.clicked.connect(fn); tb.addWidget(b)
        self.draw_btn = QPushButton("边界")
        self.draw_btn.setFixedHeight(28); self.draw_btn.setCheckable(True)
        self.draw_btn.clicked.connect(self._toggle_boundary)
        tb.addWidget(self.draw_btn)
        self.route_btn = QPushButton("路线")
        self.route_btn.setFixedHeight(28); self.route_btn.setCheckable(True)
        self.route_btn.clicked.connect(self._toggle_route)
        tb.addWidget(self.route_btn)
        tb.addStretch()
        b = QPushButton("+节点"); b.setFixedHeight(28)
        b.clicked.connect(self._on_add_node); tb.addWidget(b)
        lo.addLayout(tb)

        self.scene = MapScene(self)
        self.view = MapView(self.scene, self)
        self.view._node_ctx = self._on_node_ctx
        self.view._boundary_ctx = self._on_boundary_ctx
        self.view._route_ctx = self._on_route_ctx
        self.view._boundary_done = self._on_boundary_done
        self.view._route_done = self._on_route_done
        self.view.setStyleSheet("border:1px solid #e0e8f0; border-radius:4px;")
        lo.addWidget(self.view, 1)
        self.status = QLabel("")
        self.status.setStyleSheet("font-size:10px; color:#888; padding:0 4px;")
        lo.addWidget(self.status); self.setWidget(w)

    def _build_map(self):
        global _REBUILD
        _REBUILD = True
        self.scene.clear()
        self.view.set_node_positions(self.module.nodes)

        for n in self.module.nodes:
            if n.parent_id:
                p = next((x for x in self.module.nodes if x.id == n.parent_id), None)
                if p:
                    line = QGraphicsLineItem(QLineF(p.x, p.y, n.x, n.y))
                    line.setPen(QPen(QColor("#ccc"), 1, Qt.PenStyle.DashLine))
                    line.setZValue(1); self.scene.addItem(line)

        for rt in self.module.routes:
            c = QColor(rt.color)
            self.scene.addItem(RoutePathItem(rt.id, rt.waypoints, c, name=rt.name, description=rt.description, on_dirty=self._on_route_dirty))

        for n in self.module.nodes:
            if n.boundary and len(n.boundary) >= 3:
                cfg = NODE_TYPE_CONFIG.get(n.node_type, NODE_TYPE_CONFIG["city"])
                c = QColor(n.color or cfg["color"])
                # 绝对坐标直接传入
                self.scene.addItem(BoundaryPolygon(n.id, n.boundary, c, on_dirty=self._on_boundary_dirty))

        for n in self.module.nodes:
            item = MapNodeItem({
                "_id": n.id, "name": n.name, "node_type": n.node_type,
                "color": n.color, "x": n.x, "y": n.y,
                "radius": n.radius, "font_size": n.font_size, "font_italic": n.font_italic,
            }, on_move=self._on_node_moved)
            item.setPos(n.x, n.y)
            self.scene.addItem(item)
        _REBUILD = False

    # -- callbacks --

    def _on_boundary_dirty(self, nid, pts):
        """顶点拖拽 → 绝对坐标直接保存。"""
        global _REBUILD
        if _REBUILD: return
        self.module.update_node(nid, boundary=[[round(x, 1), round(y, 1)] for x, y in pts])
        self.module.save()

    def _on_route_dirty(self, rid, waypoints):
        global _REBUILD
        if _REBUILD: return
        self.module.update_route(rid, waypoints=[[round(x, 1), round(y, 1)] for x, y in waypoints])
        self.module.save()

    def _on_node_moved(self, nid, dx, dy):
        global _REBUILD
        if _REBUILD: return
        for n in self.module.nodes:
            if n.id == nid:
                n.x = round(n.x + dx, 1)
                n.y = round(n.y + dy, 1)
                # 边界是绝对坐标，不受节点移动影响
                self.module.save()
                break

    def _toggle_boundary(self, checked):
        self.route_btn.setChecked(False)
        if checked:
            target_id = None
            for it in self.scene.selectedItems():
                if isinstance(it, MapNodeItem):
                    target_id = self.module.find_node_id(it.node_data.get("name", ""))
                    break
            if not target_id:
                names = [n.name for n in self.module.nodes if n.name]
                if names:
                    name, ok = QInputDialog.getItem(self, "选择节点", "为哪个节点绘制边界？", names, 0, False)
                    if ok and name: target_id = self.module.find_node_id(name)
            if target_id:
                self.draw_btn.setText("绘制中"); self.status.setText("左键加点 | 点击起点封闭 | 右键完成")
                self.view.start_draw_boundary(target_id)
            else: self.draw_btn.setChecked(False)
        else:
            self.draw_btn.setText("边界"); self.status.setText(""); self.view.end_draw()

    def _toggle_route(self, checked):
        self.draw_btn.setChecked(False)
        if checked:
            self.route_btn.setText("绘制中"); self.status.setText("左键加点(吸附节点) | 右键完成")
            self.view.start_draw_route()
        else:
            self.route_btn.setText("路线"); self.status.setText(""); self.view.end_draw()

    def _on_boundary_done(self, nid, pts):
        """边界绘制完成 → 绝对坐标直接保存。"""
        self.module.update_node(nid, boundary=[[round(x, 1), round(y, 1)] for x, y in pts])
        self.module.save()
        self._build_map()
        self.draw_btn.setChecked(False); self.draw_btn.setText("边界")
        self.status.setText("边界已保存")

    def _on_route_done(self, pts):
        d = MapRouteDialog(parent=self)
        if d.exec() == QDialog.DialogCode.Accepted:
            data = d.get_data()
            if data["name"]:
                self.module.add_route(data["name"], [[round(x, 1), round(y, 1)] for x, y in pts],
                                      description=data["description"])
                self.module.save(); self._build_map()
        self.route_btn.setChecked(False); self.route_btn.setText("路线"); self.status.setText("")

    def _on_node_ctx(self, item):
        nd = item.node_data; nid = nd.get("_id", ""); name = nd.get("name", "")
        m = QMenu(self)
        rn_a = m.addAction("重命名")
        m.addSeparator()
        r_a = m.addAction(f"半径 ({nd.get('radius') or '自动'})")
        f_a = m.addAction(f"字号 ({nd.get('font_size') or '自动'})")
        i_on = nd.get("font_italic", False)
        i_a = m.addAction(f"{'取消斜体' if i_on else '斜体'}")
        m.addSeparator()
        gr = m.addAction(f"全局节点半径 ({MapNodeItem.NODE_RADIUS})")
        rs_a = m.addAction("重置样式")
        act = m.exec(QCursor.pos())
        if not act: return
        if act == rn_a:
            new_name, ok = QInputDialog.getText(self, "重命名节点", "新名称:", text=name)
            if ok and new_name.strip():
                self.module.update_node(nid, name=new_name.strip())
                self.module.save(); self._build_map()
        elif act == r_a:
            d = QInputDialog(self); d.setWindowTitle("半径")
            d.setLabelText(f"{name} 半径 (px):")
            d.setIntValue(int(nd.get("radius") or NODE_TYPE_CONFIG.get(nd.get("node_type", "city"), {}).get("size", 8)))
            d.setIntRange(0, 60)
            if d.exec(): self.module.update_node(nid, radius=d.intValue()); self.module.save(); self._build_map()
        elif act == gr:
            d = QInputDialog(self); d.setWindowTitle("全局节点半径")
            d.setLabelText("所有节点的显示半径 (0=使用各自设置):")
            d.setIntValue(MapNodeItem.NODE_RADIUS); d.setIntRange(0, 60)
            if d.exec(): MapNodeItem.NODE_RADIUS = d.intValue(); self._build_map()
        elif act == f_a:
            d = QInputDialog(self); d.setWindowTitle("字号")
            d.setLabelText(f"{name} 字号:"); d.setIntValue(int(nd.get("font_size") or 9)); d.setIntRange(1, 48)
            if d.exec(): self.module.update_node(nid, font_size=d.intValue()); self.module.save(); self._build_map()
        elif act == i_a:
            self.module.update_node(nid, font_italic=not i_on); self.module.save(); self._build_map()
        elif act == rs_a:
            self.module.update_node(nid, radius=0, font_size=0, font_italic=False); self.module.save(); self._build_map()

    def _on_boundary_ctx(self, item):
        if isinstance(item, BoundaryVertex):
            m = QMenu(self); dv = m.addAction("删除此顶点")
            m.addSeparator()
            vr = m.addAction(f"顶点半径 ({BoundaryVertex.VERTEX_RADIUS})")
            act = m.exec(QCursor.pos())
            if act == dv:
                bp = item.parentItem() if isinstance(item.parentItem(), BoundaryPolygon) else None
                if not bp: return
                pts = bp._collect_pts()
                if len(pts) > 3:
                    pts.pop(item._idx)
                    # 绝对坐标直接保存
                    self.module.update_node(bp._node_id, boundary=[[round(x, 1), round(y, 1)] for x, y in pts])
                    self.module.save(); self._build_map()
                else: QMessageBox.information(self, "提示", "至少需要 3 个顶点")
            elif act == vr:
                d = QInputDialog(self); d.setWindowTitle("顶点半径")
                d.setLabelText("所有顶点的显示半径 (0=隐藏):")
                d.setIntValue(BoundaryVertex.VERTEX_RADIUS); d.setIntRange(0, 10)
                if d.exec(): BoundaryVertex.VERTEX_RADIUS = d.intValue(); self._build_map()
            return
        if isinstance(item, BoundaryPolygon):
            m = QMenu(self); db = m.addAction("删除整个边界")
            if m.exec(QCursor.pos()) == db:
                self.module.update_node(item._node_id, boundary=[])
                self.module.save(); self._build_map()
            return

    def _on_route_ctx(self, item):
        m = QMenu(self)
        m.addAction(f"名称: {item._name}{' - ' + item._description[:50] if item._description else ''}")
        m.addSeparator()
        rn_r = m.addAction("重命名")
        dr = m.addAction("删除此路线")
        act = m.exec(QCursor.pos())
        if act == rn_r:
            new_name, ok = QInputDialog.getText(self, "重命名路线", "新名称:", text=item._name)
            if ok and new_name.strip():
                self.module.update_route(item._route_id, name=new_name.strip())
                self.module.save(); self._build_map()
        elif act == dr:
            self.module.delete_route(item._route_id)
            self.module.save(); self._build_map()

    def _fit_view(self): self.view.fit_all()
    def _zoom_view(self, f): self.view.scale(f, f)
    def _refresh(self): self._build_map()

    def _on_add_node(self):
        d = MapNodeDialog()
        if d.exec() == QDialog.DialogCode.Accepted:
            data = d.get_data()
            if data["name"]:
                self.module.add_node(**data)
                self.module.save(); self._build_map()
