// Отчёты администратора: результаты группы и карточка студента (роза ветров и ПК → ОТФ).

import { api, byCode, fill, go, h, masteryBadge, screenAt } from "../core.js";
import { profileCharts } from "../radar.js";
import { laborFunctionsView } from "../reports.js";
import { loadTests, withDirection } from "./directions.js";

// Выбор переживает уход в карточку студента и возврат.
let lastGroup = "";
let lastTest = "";

export const adminGroupResults = withDirection("Результаты", async (render, direction) => {
  const [groups, tests] = await Promise.all([api(`/groups?direction_id=${direction.id}`), loadTests(direction)]);
  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const test = h("select", { "aria-label": "Тест" });
  const excel = h("a", { class: "button", download: "" }, "Скачать Excel");
  // Отчет по форме кафедры – по одному тесту.
  const word = h("a", { class: "button", download: "", title: "Результаты проверки уровня сформированности компетенций (форма кафедры)" }, "Отчет по тесту (Word)");
  const out = h("div", { class: "table-wrap" });
  const whom = h("select", { "aria-label": "Чья роза" });
  const charts = h("div");
  const radarHint = h("p", { class: "notice" },
    "Появится, когда студенты сдадут тест: назначьте его в «Тесты → Новый тест», студент проходит его в «Мои тесты». Для диаграммы нужно минимум 3 компетенции.");
  const radarSection = h("section", {},
    h("h2", {}, "Роза ветров"),
    h("div", { class: "card" },
      h("div", {}, h("label", {}, "Чьи результаты"), whom),
      h("p", { class: "muted small" }, "Шкала 0–5: 5 – все ответы верные. Уровень трудовой функции – среднее по связанным с ней компетенциям, которые проверялись."),
      radarHint,
    ),
    charts,
  );
  const toRadar = h("button", {
    type: "button", class: "link",
    onclick: () => radarSection.scrollIntoView({ behavior: "smooth", block: "start" }),
  }, "Роза ветров ↓");
  let report = null;

  function drawTests() {
    const groupId = Number(group.value);
    fill(test,
      h("option", { value: "" }, "Все пройденные тесты"),
      tests.filter((t) => t.group_ids.includes(groupId)).map((t) => h("option", { value: t.id }, t.title)));
  }

  const query = () => (test.value ? `?test_id=${test.value}` : "");

  async function drawCharts() {
    const studentId = whom.value;
    const params = new URLSearchParams();
    if (test.value) params.set("test_id", test.value);
    if (studentId) params.set("student_id", studentId);
    const profile = await api(`/reports/groups/${group.value}/profile?${params}`);
    const who = studentId
      ? report.students.find((s) => s.student_id === Number(studentId)).full_name
      : `группа ${report.name}, среднее`;
    fill(charts, profileCharts(profile, who));
  }

  async function draw() {
    const [loaded, settings] = await Promise.all([
      api(`/reports/groups/${group.value}/competencies${query()}`),
      api("/settings"),
    ]);
    report = loaded;
    excel.href = `/reports/groups/${group.value}/competencies.xlsx${query()}`;
    word.href = `/reports/groups/${group.value}/results.docx${query()}`;
    const codes = [...new Set(report.students.flatMap((s) => s.competencies.map((c) => c.code)))].sort(byCode);
    const tested = report.students.filter((s) => s.competencies.length);
    fill(whom,
      h("option", { value: "" }, "Вся группа (среднее)"),
      tested.map((s) => h("option", { value: s.student_id }, s.full_name)));
    if (!codes.length) {
      fill(out, h("p", { class: "muted" }, test.value ? "Этот тест группа ещё не проходила" : "Группа ещё не проходила тесты"));
      fill(charts);
      excel.hidden = word.hidden = true;
      whom.parentElement.hidden = true;
      radarHint.hidden = false;
      return;
    }
    excel.hidden = false;
    word.hidden = !test.value;
    whom.parentElement.hidden = false;
    radarHint.hidden = true;
    fill(out,
      h("p", { class: "muted small mt-0" },
        `«N из M» – верных ответов из заданных. Зелёным – компетенция сформирована (от ${Math.round(settings.mastery_threshold * 100)}% верных; порог меняется в «Система → Настройки»).`),
      h("table", {},
        h("tr", {}, h("th", {}, "Студент"), h("th", {}, "Дата"), codes.map((c) => h("th", {}, c))),
        report.students.map((s) => {
          const byCode = new Map(s.competencies.map((c) => [c.code, c]));
          return h("tr", {},
            h("td", {}, s.competencies.length
              ? h("button", { class: "link bare text-left", title: "Карточка студента", onclick: () => go(studentCard(s.student_id)) }, s.full_name)
              : s.full_name),
            h("td", {}, s.tested_at ? new Date(s.tested_at).toLocaleDateString("ru-RU") : h("span", { class: "muted" }, "–")),
            codes.map((c) => h("td", {}, byCode.has(c) ? masteryBadge(byCode.get(c)) : h("span", { class: "muted" }, "–"))),
          );
        }),
      ),
    );
    await drawCharts();
  }

  group.addEventListener("change", () => { lastGroup = group.value; lastTest = ""; drawTests(); draw(); });
  test.addEventListener("change", () => { lastTest = test.value; draw(); });
  whom.addEventListener("change", drawCharts);
  render(
    h("h1", {}, "Результаты группы"),
    h("div", { class: "card" },
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Группа"), group),
        h("div", { class: "grow" }, h("label", {}, "Тест"), test),
        h("div", { class: "row" }, excel, word),
        h("div", { class: "pad-bottom" }, toRadar),
      ),
    ),
    h("div", { class: "card" }, out),
    radarSection,
  );
  if (groups.length) {
    if (groups.some((g) => String(g.id) === lastGroup)) group.value = lastGroup;
    drawTests();
    if (lastTest) test.value = lastTest; // нет такого теста в списке – остаётся «Все»
    await draw();
  }
});

// Карточка студента: роза ветров и трудовые функции. Адрес #/results/student/<id>.
export function studentCard(id) {
  return screenAt(`results/student/${id}`, async (render) => {
    const student = (await api("/students")).find((st) => st.id === id);
    if (!student) return render(h("h1", {}, "Студент не найден"));
    const [profile, laborFunctions] = await Promise.all([
      api(`/reports/groups/${student.group_id}/profile?student_id=${id}`),
      api(`/reports/students/${id}/labor-functions`),
    ]);
    render(
      h("h1", {}, student.full_name),
      h("p", {}, h("button", { class: "link bare", onclick: () => go(adminGroupResults) }, "← Результаты группы")),
      profileCharts(profile, student.full_name),
      h("h2", {}, "ПК → ОТФ: трудовые функции"),
      h("p", { class: "muted" }, "ТФ закрыта, если сформированы все связанные с ней компетенции."),
      laborFunctionsView(laborFunctions),
    );
  }, adminGroupResults);
}
