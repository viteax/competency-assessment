// Студенты группы и их учётные записи.

import { api, errorBox, fill, h, render } from "../core.js";

export async function adminStudents() {
  const groups = await api("/groups");
  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const table = h("div", { class: "table-wrap" });
  const err = errorBox();
  const ok = h("div", { class: "success" });

  async function drawStudents() {
    const [students, users] = await Promise.all([
      api(`/students?group_id=${group.value}`),
      api("/users"),
    ]);
    const logins = new Map(users.filter((u) => u.student_id).map((u) => [u.student_id, u.username]));
    fill(table,
      students.length
        ? h("table", {},
            h("tr", {}, h("th", {}, "ФИО"), h("th", {}, "Логин")),
            students.map((s) =>
              h("tr", {}, h("td", {}, s.full_name), h("td", {}, logins.get(s.id) || h("span", { class: "muted" }, "нет"))),
            ),
          )
        : h("p", { class: "muted" }, "В группе пока нет студентов"),
    );
  }
  group.addEventListener("change", drawStudents);

  const fullName = h("input", { type: "text", required: true });
  const username = h("input", { type: "text", required: true, minlength: 3 });
  const password = h("input", { type: "text", required: true, minlength: 6 });

  render(
    h("h1", {}, "Студенты"),
    h("div", { class: "card" }, h("label", {}, "Группа"), group, h("h2", {}, "Список"), table),
    h(
      "form",
      {
        class: "card",
        onsubmit: async (event) => {
          event.preventDefault();
          err.clear();
          ok.textContent = "";
          try {
            const student = await api("/students", {
              method: "POST",
              body: { full_name: fullName.value, group_id: Number(group.value) },
            });
            await api("/users", {
              method: "POST",
              body: {
                username: username.value,
                password: password.value,
                role: "student",
                student_id: student.id,
              },
            });
            ok.textContent = `Добавлен ${student.full_name}, логин ${username.value}`;
            fullName.value = username.value = password.value = "";
            await drawStudents();
          } catch (e) {
            err.show(e);
          }
        },
      },
      h("h2", { style: "margin-top:0" }, "Добавить студента в выбранную группу"),
      h("label", {}, "ФИО"),
      fullName,
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Логин"), username),
        h("div", {}, h("label", {}, "Пароль"), password),
      ),
      h("div", { style: "margin-top:16px" }, h("button", { class: "primary" }, "Добавить")),
      err.el,
      ok,
    ),
  );
  if (groups.length) await drawStudents();
}
