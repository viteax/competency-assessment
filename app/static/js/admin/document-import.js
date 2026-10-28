// Загрузка документа одним полем: система сама понимает, что это – учебный план из «Планов»
// или документ ОПОП / РПД.

import { errorBox, fill, h } from "../core.js";
import { activeDirection } from "./directions.js";
import { previewCompetencies } from "./import.js";
import { previewPlan } from "./plan-import.js";

export function documentImportView() {
  const err = errorBox();
  const file = h("input", { type: "file", accept: ".docx,.xlsx,.pdf,.txt", required: true, "aria-label": "Файл документа" });
  const previewSlot = h("div");

  async function upload(event) {
    event.preventDefault();
    err.clear();
    fill(previewSlot);
    if (!file.files.length) return;
    let planError = null;
    // Учебный план – всегда .xlsx; остальные файлы сразу идут как ОПОП / РПД.
    if (file.files[0].name.toLowerCase().endsWith(".xlsx")) {
      try {
        return await previewPlan(file, previewSlot);
      } catch (e) {
        planError = e;
      }
    }
    try {
      const direction = await activeDirection();
      if (!direction) throw new Error("для документа ОПОП / РПД нужно направление: загрузите учебный план или добавьте направление в «Система → Направления»");
      await previewCompetencies(direction, file, previewSlot);
    } catch (e) {
      // Сервер, узнав в файле учебный план, отсылает на старую вкладку; тогда важнее ошибка разбора плана.
      err.show(planError && e.message.includes("«Планов»") ? planError : e);
    }
  }

  return [
    h("form", { class: "card", onsubmit: upload },
      h("p", { class: "muted mt-0" },
        "Загрузите учебный план из «Планов» (Excel, файл вида 09.03.01_2023_….plx.xlsx) или документ ОПОП / РПД ",
        "(.docx, .xlsx, .pdf, .txt) – тип система определит сама. Перед сохранением результат можно проверить и поправить; ничего не удаляется."),
      file,
      h("div", { class: "mt-m" }, h("button", { class: "primary" }, "Разобрать файл")),
      err.el,
    ),
    previewSlot,
  ];
}
