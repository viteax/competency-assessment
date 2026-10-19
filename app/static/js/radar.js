// «Роза ветров» (лепестковая диаграмма): уровень по компетенциям или трудовым функциям
// на пятибалльной шкале. SVG без библиотек; подсказка при наведении; выгрузка в JPEG, PNG,
// Word и печать (PDF – через «Сохранить как PDF» в окне печати браузера).

import { h } from "./core.js";

const SVG = "http://www.w3.org/2000/svg";
const MAX = 5; // шкала: 5 – все ответы верные
const SIZE = 460;
const CENTER = SIZE / 2;
const RADIUS = 150;
const LINE = 20; // высота строки подписи под диаграммой на картинке

// Для картинок – всегда светлая палитра: картинку вставляют в отчёты на белом фоне.
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
// withTitle – подписать диаграмму, legend – строки подписи под ней (для картинок: на
// странице заголовок и подпись есть в карточке).
function radarSvg(title, axes, palette, onHover, withTitle = false, legend = []) {
  const n = axes.length;
  const height = SIZE + (legend.length ? legend.length * LINE - 4 : 0);
  const svg = s("svg", {
    viewBox: `0 0 ${SIZE} ${height}`, width: SIZE, height, role: "img",
    "aria-label": `${title}: ${axes.map((a) => `${a.label} ${score(a.value)} из ${MAX}`).join(", ")}`,
    "font-family": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  });
  svg.append(s("rect", { width: SIZE, height, fill: palette.surface }));
  legend.forEach((line, i) => {
    svg.append(s("text", {
      x: CENTER, y: SIZE - 14 + i * LINE, "text-anchor": "middle", "font-size": 13, fill: palette.text,
    }, line));
  });
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

function save(blob, filename) {
  const link = h("a", { href: URL.createObjectURL(blob), download: filename });
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

// Картинка диаграммы с заголовком и подписью; type – image/png или image/jpeg.
async function chartImage(title, axes, legend, type) {
  const svg = radarSvg(title, axes, LIGHT, null, true, legend);
  const width = SIZE;
  const height = Number(svg.getAttribute("height"));
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], { type: "image/svg+xml" }));
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const canvas = document.createElement("canvas");
    canvas.width = width * 2; // чёткость при печати
    canvas.height = height * 2;
    const ctx = canvas.getContext("2d");
    ctx.scale(2, 2);
    ctx.drawImage(img, 0, 0);
    return await new Promise((resolve) => canvas.toBlob(resolve, type, 0.92));
  } finally {
    URL.revokeObjectURL(url);
  }
}

const base64 = (blob) => new Promise((resolve) => {
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result);
  reader.readAsDataURL(blob);
});

// Word собирает сервер: картинка, подпись и таблица значений по осям.
async function downloadDocx(title, axes, legend, filename) {
  const image = await base64(await chartImage(title, axes, [], "image/png"));
  const response = await fetch("/charts/docx", {
    method: "POST",
    headers: { "X-Requested-With": "fetch", "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({
      title, legend, image,
      rows: axes.map((a) => [a.label, a.name || "", `${score(a.value)} из ${MAX}`]),
    }),
  });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || response.statusText);
  save(await response.blob(), `${filename}.docx`);
}

// Печать одной карточки: остальная страница скрывается стилями @media print.
function printCard(card) {
  card.classList.add("print-target");
  document.body.classList.add("print-one");
  const done = () => {
    card.classList.remove("print-target");
    document.body.classList.remove("print-one");
    window.removeEventListener("afterprint", done);
  };
  window.addEventListener("afterprint", done);
  window.print();
}

// Карточка с диаграммой. axes без значения (value === null) не рисуются, а перечисляются
// под диаграммой как «нет данных»; для лепестковой диаграммы нужно минимум 3 оси.
export function radarCard(title, axes, filename, legend = []) {
  const drawn = axes.filter((a) => a.value !== null);
  const missing = axes.filter((a) => a.value === null);
  const tip = h("div", { class: "radar-tip", hidden: true });
  const wrap = h("div", { class: "radar-wrap" });
  const err = h("p", { class: "error", role: "alert" });
  const card = h("div", { class: "card radar-card" });
  const run = (fn) => async () => {
    err.textContent = "";
    try {
      await fn();
    } catch (e) {
      err.textContent = e.message;
    }
  };

  let body;
  if (drawn.length >= 3) {
    wrap.append(radarSvg(title, drawn, screenPalette(), (axis, x, y) => {
      if (!axis) return (tip.hidden = true);
      tip.textContent = `${axis.label}: ${score(axis.value)} из ${MAX}${axis.hint ? ` – ${axis.hint}` : ""}`;
      const scale = wrap.clientWidth / SIZE;
      tip.style.left = `${x * scale}px`;
      tip.style.top = `${y * scale}px`;
      tip.hidden = false;
    }), tip);
    const image = (type, ext) => run(async () => save(await chartImage(title, drawn, legend, type), `${filename}.${ext}`));
    body = [
      wrap,
      h("div", { class: "row no-print", style: "gap:8px;flex-wrap:wrap" },
        h("button", { type: "button", onclick: image("image/jpeg", "jpg") }, "JPEG"),
        h("button", { type: "button", onclick: image("image/png", "png") }, "PNG"),
        h("button", { type: "button", onclick: run(() => downloadDocx(title, drawn, legend, filename)) }, "Word"),
        h("button", { type: "button", onclick: () => printCard(card) }, "Печать / PDF"),
      ),
      err,
    ];
  } else {
    body = h("p", { class: "muted" },
      drawn.length
        ? `Для диаграммы нужно минимум 3 оси, сейчас ${drawn.length}: ${drawn.map((a) => `${a.label} – ${score(a.value)} из ${MAX}`).join("; ")}.`
        : "Пока нет результатов.");
  }
  card.append(
    h("h2", { style: "margin-top:0" }, title),
    legend.length ? h("p", { class: "muted small radar-legend" }, legend.map((line, i) => [i ? h("br") : null, line])) : "",
    ...[body].flat(),
    drawn.length ? h("table", { class: "small" },
      drawn.map((a) => h("tr", {}, h("td", {}, a.label), h("td", { class: "wrap" }, a.name || ""), h("td", {}, `${score(a.value)} из ${MAX}`)))) : "",
    missing.length ? h("p", { class: "muted small" }, "Нет данных (не проверялись): ", missing.map((a) => a.label).join(", ")) : "",
  );
  return card;
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
    radarCard(`Компетенции – ${who}`, competencies, `Компетенции – ${who}`, profile.legend),
    radarCard(`Трудовые функции – ${who}`, functions, `Трудовые функции – ${who}`, profile.legend),
  );
}
