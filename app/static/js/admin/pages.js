// Разделы администратора со вкладками. Порядок разделов и вкладок – порядок работы кафедры:
// подготовить направление, наполнить банк, собрать и назначить тест, посмотреть результаты.

import { h, screenTab, tabbedPage } from "../core.js";
import { adminAssign } from "./assign.js";
import { adminAudit } from "./audit.js";
import { CATALOGS } from "./catalogs.js";
import { directionTab } from "./directions.js";
import { documentImportView } from "./document-import.js";
import { studentImportView } from "./import.js";
import { adminStudents } from "./students.js";
import { adminTests } from "./tests.js";

// Пояснение над вкладкой: что здесь хранится и на что влияет.
const intro = (text, tab) => async () => [h("p", { class: "muted" }, text), await tab()];

export const prepPage = tabbedPage("Подготовка", {
  "Загрузить документ": intro("Самый быстрый старт: учебный план из «Планов» (.plx.xlsx) сразу заполняет направление, компетенции, дисциплины с семестрами и статусом, профстандарты и связи ТФ ⇒ компетенции. Документ ОПОП или РПД добавляет индикаторы компетенций и компетенции дисциплины в направление, выбранное в шапке.", documentImportView),
  "Компетенции": intro("Компетенции ФГОС (УК, ОПК, ПК) направления из шапки с формулировками. У каждого направления свои: коды в разных ОП совпадают, а формулировки бывают разные. Их проще загрузить из учебного плана, ОПОП или РПД – вкладка «Загрузить документ».", directionTab(CATALOGS["Компетенции"])),
  "Дисциплины": intro("Дисциплины направления, их статус в учебном плане и компетенции, которые они формируют. По ним преподаватели составляют вопросы.", directionTab(CATALOGS["Дисциплины"])),
  "Учебный план и преподаватели": directionTab(CATALOGS["Учебный план"]),
  "ТФ ⇒ компетенции": directionTab(CATALOGS["ТФ ⇒ компетенции"]),
});

export const testsPage = tabbedPage("Тесты", {
  "Новый тест": screenTab(adminAssign),
  "Все тесты": screenTab(adminTests),
});

export const peoplePage = tabbedPage("Люди", {
  "Группы": intro("Академические группы направления из шапки. Год набора нужен, чтобы считать текущий семестр группы.", directionTab(CATALOGS["Группы"])),
  "Студенты": screenTab(adminStudents),
  "Преподаватели": CATALOGS["Преподаватели"],
  "Загрузить список": studentImportView,
});

export const systemPage = tabbedPage("Система", {
  "Направления": intro("Направления подготовки кафедры: код и название, например 09.03.04 «Программная инженерия». Какое из них открыто в кабинете, выбирается в шапке.", CATALOGS["Направления"]),
  "Профстандарты": intro("Профессиональные стандарты, на которые ориентированы компетенции. Общие для всех направлений.", CATALOGS["Профстандарты"]),
  "ОТФ": intro("Обобщённые трудовые функции профстандартов. Общие для всех направлений.", CATALOGS["ОТФ"]),
  "Настройки": CATALOGS["Настройки"],
  "Журнал": screenTab(adminAudit),
});
