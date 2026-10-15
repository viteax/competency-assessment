// «Роза ветров» (лепестковая диаграмма): уровень по компетенциям или трудовым функциям
// на пятибалльной шкале. SVG без библиотек; подсказка при наведении; выгрузка в PNG.

import { h } from "./core.js";

const SVG = "http://www.w3.org/2000/svg";
const MAX = 5; // шкала: 5 — все ответы верные
const SIZE = 460;
const CENTER = SIZE / 2;
const RADIUS = 150;

// Для PNG — всегда светлая палитра: картинку вставляют в отчёты на белом фоне.
const LIGHT = { surface: "#ffffff", text: "#1d2330", muted: "#6b7280", grid: "#e3e6eb", series: "#2a78d6" };

function s(tag, attrs = {}, ...children) {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  el.append(...children);
  return el;
}

function screenPalette() {
  const css = getComputedStyle(document.documentElement);
  const v = (name) => css.getPropertyValue(name).trim();
  return { surface: v("--card"), text: v("--text"), muted: v("--muted"), grid: v("--border"), series: v("--series-1") };
}

const score = (value) => (value * MAX).toLocaleString("ru-RU", { maximumFractionDigits: 1 });
const point = (i, n, r) => {
  const angle = -Math.PI / 2 + (2 * Math.PI * i) / n; // первая ось — вверх, по часовой
  return [CENTER + r * Math.cos(angle), CENTER + r * Math.sin(angle)];
};

// axes: [{ label, value (0..1), hint }]
// withTitle — подписать диаграмму (для PNG: на странице заголовок есть в карточке).
function radarSvg(title, axes, palette, onHover, withTitle = false) {
  const n = axes.length;
  const svg = s("svg", {
    viewBox: `0 0 ${SIZE} ${SIZE}`, width: SIZE, height: SIZE, role: "img",
    "aria-label": `${title}: ${axes.map((a) => `${a.label} ${score(a.value)} из ${MAX}`).join(", ")}`,
    "font-family": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  });
  svg.append(s("rect", { width: SIZE, height: SIZE, fill: palette.surface }));
  if (withTitle) {
    svg.append(s("text", {
      x: CENTER, y: 26, "text-anchor": "middle", "font-size": 15, "font-weight": 600, fill: palette.text,
    }, title));
  }

  // Сетка: кольца 1..5 и лучи — тонкие и бледные, чтобы не спорить с данными.
  for (let ring = 1; ring <= MAX; ring++) {
    const pts = axes.map((_, i) => point(i, n, (RADIUS * ring) / MAX).join(",")).join(" ");
    svg.append(s("polygon", { points: pts, fill: "none", stroke: palette.grid, "stroke-width": 1 }));
    const [x, y] = point(0, n, (RADIUS * ring) / MAX);
    svg.append(s("text", { x: x - 6, y: y + 4, "text-anchor": "end", "font-size": 11, fill: palette.muted }, String(ring)));
  }
  axes.forEach((a, i) => {
    const [x, y] = point(i, n, RADIUS);
    svg.append(s("line", { x1: CENTER, y1: CENTER, x2: x, y2: y, stroke: palette.grid, "stroke-width": 1 }));
    const [lx, ly] = point(i, n, RADIUS + 22);
    const anchor = Math.abs(lx - CENTER) < 8 ? "middle" : lx > CENTER ? "start" : "end";
    svg.append(s("text", {
      x: lx, y: ly + 4, "text-anchor": anchor, "font-size": 13, "font-weight": 600, fill: palette.text,
    }, a.label));
  });

  // Данные: полупрозрачная заливка, линия 2px, точки 8px с кольцом цвета фона.
  const pts = axes.map((a, i) => point(i, n, RADIUS * a.value));
  svg.append(s("polygon", {
    points: pts.map((p) => p.join(",")).join(" "),
    fill: palette.series, "fill-opacity": 0.18, stroke: palette.series, "stroke-width": 2, "stroke-linejoin": "round",
  }));
  pts.forEach(([x, y], i) => {
    svg.append(s("circle", { cx: x, cy: y, r: 4, fill: palette.series, stroke: palette.surface, "stroke-width": 2 }));
    if (onHover) {
      // Зона наведения больше самой точки.
      svg.append(s("circle", {
        cx: x, cy: y, r: 14, fill: "transparent", tabindex: 0,
        onmouseenter: () => onHover(axes[i], x, y), onfocus: () => onHover(axes[i], x, y),
        onmouseleave: () => onHover(null), onblur: () => onHover(null),
      }));
    }
  });
  return svg;
}

async function downloadPng(title, axes, filename) {
  const svg = radarSvg(title, axes, LIGHT, null, true);
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], { type: "image/svg+xml" }));
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = SIZE * 2; // чёткость при печати
    const ctx = canvas.getContext("2d");
    ctx.scale(2, 2);
    ctx.drawImage(img, 0, 0);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    const link = h("a", { href: URL.createObjectURL(blob), download: filename });
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  } finally {
    URL.revokeObjectURL(url);
  }
}

// Карточка с диаграммой. axes без значения (value === null) не рисуются, а перечисляются
// под диаграммой как «нет данных»; для лепестковой диаграммы нужно минимум 3 оси.
export function radarCard(title, axes, filename) {
  const drawn = axes.filter((a) => a.value !== null);
  const missing = axes.filter((a) => a.value === null);
  const tip = h("div", { class: "radar-tip", hidden: true });
  const wrap = h("div", { class: "radar-wrap" });

  let body;
  if (drawn.length >= 3) {
    wrap.append(radarSvg(title, drawn, screenPalette(), (axis, x, y) => {
      if (!axis) return (tip.hidden = true);
      tip.textContent = `${axis.label}: ${score(axis.value)} из ${MAX}${axis.hint ? ` — ${axis.hint}` : ""}`;
      const scale = wrap.clientWidth / SIZE;
      tip.style.left = `${x * scale}px`;
      tip.style.top = `${y * scale}px`;
      tip.hidden = false;
    }), tip);
    body = [
      wrap,
      h("button", { type: "button", onclick: () => downloadPng(title, drawn, filename) }, "Скачать PNG"),
    ];
  } else {
    body = h("p", { class: "muted" },
      drawn.length
        ? `Для диаграммы нужно минимум 3 оси, сейчас ${drawn.length}: ${drawn.map((a) => `${a.label} — ${score(a.value)} из ${MAX}`).join("; ")}.`
        : "Пока нет результатов.");
  }
  return h("div", { class: "card radar-card" },
    h("h2", { style: "margin-top:0" }, title),
    body,
    drawn.length ? h("table", { class: "small" },
      drawn.map((a) => h("tr", {}, h("td", {}, a.label), h("td", { class: "wrap" }, a.name || ""), h("td", {}, `${score(a.value)} из ${MAX}`)))) : null,
    missing.length ? h("p", { class: "muted small" }, "Нет данных (не проверялись): ", missing.map((a) => a.label).join(", ")) : null,
  );
}

// Две «розы» по ответу /…/profile: компетенции и трудовые функции.
export function profileCharts(profile, who) {
  const competencies = profile.competencies.map((c) => ({
    label: c.code, name: c.name, value: c.value,
    hint: c.total > 1 ? `проверено у ${c.measured} из ${c.total} студентов` : "",
  }));
  const functions = profile.labor_functions.map((f) => ({
    label: f.code, name: f.name, value: f.value,
    hint: f.measured < f.total ? `проверено компетенций: ${f.measured} из ${f.total}` : "",
  }));
  return h("div", { class: "radar-grid" },
    radarCard(`Компетенции — ${who}`, competencies, `Компетенции — ${who}.png`),
    radarCard(`Трудовые функции — ${who}`, functions, `Трудовые функции — ${who}.png`),
  );
}
