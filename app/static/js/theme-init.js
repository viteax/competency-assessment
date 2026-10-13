// Применяем выбранную тему до отрисовки, чтобы не было вспышки другой темы.
// Отдельный файл, а не inline-скрипт: политика безопасности (CSP) запрещает inline-код.
try {
  const theme = localStorage.getItem("theme");
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
} catch {
  /* приватный режим */
}
