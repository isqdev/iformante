import { expect, test, type Page } from "@playwright/test";

type Role = "guest" | "COMMON" | "ADMIN" | "SUPER";
const initial = [
  { id: "router001", param: "prompt_router", value: "## Instruções do Router\n\nEscolha **documentos** quando necessário." },
  { id: "rerank001", param: "prompt_reranker", value: "## Ordem dos trechos\n\nRetorne JSON." },
  { id: "replier01", param: "prompt_replier", value: "Responda com as fontes." },
  { id: "style0001", param: "prompt_speech_style", value: "Fale naturalmente em até {{max_words}} palavras." },
  { id: "voice0001", param: "prompt_replier_voice", value: "Responda na chamada. {{speech_style}}" },
  { id: "rewrite01", param: "prompt_voice_rewrite", value: "Adapte para fala. {{speech_style}}" },
];

async function fixtures(page: Page, role: Role, conflict = false) {
  const prompts = initial.map((prompt) => ({ ...prompt }));
  const changes: { path: string; body: Record<string, string> }[] = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === "/api/auth/me") return route.fulfill({ json: role === "guest" ? null : { id: "isaque123", first_name: "Isaque", role } });
    if (url.pathname === "/api/conversations") return route.fulfill({ json: [] });
    if (url.pathname === "/api/system/prompts") return route.fulfill({ json: prompts });
    if (url.pathname.startsWith("/api/system/prompts/")) {
      const body = request.postDataJSON();
      changes.push({ path: url.pathname, body });
      const prompt = prompts.find((item) => url.pathname.endsWith(item.param))!;
      if (conflict) {
        conflict = false;
        prompt.value = "Versão salva por outra aba.";
        return route.fulfill({ status: 409, json: { detail: "Este prompt mudou desde que você abriu o editor." } });
      }
      prompt.value = body.value;
      return route.fulfill({ json: prompt });
    }
    if (url.pathname === "/api/system/users/role") {
      const body = request.postDataJSON();
      changes.push({ path: url.pathname, body });
      return route.fulfill({ json: { role: body.role, message: body.role === "SUPER" ? "Administrador promovido a SUPER com sucesso." : "SUPER rebaixado a administrador com sucesso." } });
    }
    return route.fulfill({ json: [] });
  });
  return changes;
}

for (const role of ["COMMON", "ADMIN"] as const) {
  test(`${role} não acessa Sistema nem vê o botão na sidebar`, async ({ page }) => {
    await fixtures(page, role);
    await page.goto("/system", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Acesso exclusivo para SUPER.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sistema", exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Prompt Hub" })).toHaveCount(0);
  });
}

test("visitante é encaminhado ao login", async ({ page }) => {
  await fixtures(page, "guest");
  await page.goto("/system");
  await expect(page).toHaveURL("/login");
});

test("SUPER visualiza Markdown, edita e salva o texto bruto", async ({ page }) => {
  const changes = await fixtures(page, "SUPER");
  await page.goto("/system");
  await expect(page.getByRole("button", { name: "Sistema", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Novo documento", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Instruções do Router" })).toBeVisible();
  await page.getByRole("button", { name: "Editar", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Router", exact: true })).toHaveValue(initial[0].value);
  const value = "## Router atualizado\n\nTexto **novo**.\n";
  await page.getByRole("textbox", { name: "Router", exact: true }).fill(value);
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Router atualizado" })).toBeVisible();
  await expect(page.getByText("Prompt atualizado com sucesso.")).toBeVisible();
  expect(changes[0].body).toEqual({ value, expected_value: initial[0].value });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Router atualizado" })).toBeVisible();
});

test("alternar grupos preserva rascunho; cancelar descarta sem salvar", async ({ page }) => {
  const changes = await fixtures(page, "SUPER");
  await page.goto("/system");
  await page.getByRole("button", { name: "Editar", exact: true }).click();
  await page.getByRole("textbox", { name: "Router", exact: true }).fill("Rascunho");
  await page.getByRole("button", { name: "Replier", exact: true }).click();
  await expect(page.getByText("Estilo de voz", { exact: true })).toBeVisible();
  await expect(page.getByText("Resposta de voz", { exact: true })).toBeVisible();
  await expect(page.getByText("Adaptação para voz", { exact: true })).toBeVisible();
  await expect(page.getByText("Nova tentativa", { exact: false })).toHaveCount(0);
  await page.getByRole("button", { name: "Router", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Router", exact: true })).toHaveValue("Rascunho");
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Instruções do Router" })).toBeVisible();
  expect(changes).toHaveLength(0);
});

test("conflito preserva rascunho e permite revisar a versão atual", async ({ page }) => {
  const changes = await fixtures(page, "SUPER", true);
  await page.goto("/system");
  await page.getByRole("button", { name: "Editar", exact: true }).click();
  await page.getByRole("textbox", { name: "Router", exact: true }).fill("Meu rascunho");
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(page.locator("#prompt_router-error")).toContainText("Este prompt mudou");
  await expect(page.getByRole("textbox", { name: "Router", exact: true })).toHaveValue("Meu rascunho");
  await page.getByRole("button", { name: "Recarregar versão salva" }).click();
  await expect(page.locator("#prompt_router-error")).toContainText("rascunho foi preservado");
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(page.getByText("Prompt atualizado com sucesso.")).toBeVisible();
  expect(changes[1].body.expected_value).toBe("Versão salva por outra aba.");
});

test("promover e rebaixar usa e-mail e confirma sucesso; cancelar não altera", async ({ page }) => {
  const changes = await fixtures(page, "SUPER");
  await page.goto("/system");
  for (const [action, role] of [["Promover", "SUPER"], ["Rebaixar", "ADMIN"]] as const) {
    await page.getByRole("button", { name: action, exact: true }).click();
    await page.getByRole("textbox", { name: "E-mail institucional" }).fill("admin@ifpr.edu.br");
    await page.getByRole("button", { name: "Confirmar", exact: true }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(changes.at(-1)?.body).toEqual({ email: "admin@ifpr.edu.br", role });
  }
  await expect(page.getByText("SUPER rebaixado a administrador com sucesso.")).toBeVisible();
  await page.getByRole("button", { name: "Promover", exact: true }).click();
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  expect(changes).toHaveLength(2);
});

for (const width of [320, 1440]) {
  test(`Sistema responsivo em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await fixtures(page, "SUPER");
    await page.goto("/system");
    await expect(page.getByRole("heading", { name: "Instruções do Router" })).toBeVisible();
    await page.getByRole("button", { name: "Replier", exact: true }).click();
    await expect(page.getByText("Estilo de voz", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.screenshot({ path: `test-results/screens/system-${width}.png`, fullPage: true, animations: "disabled" });
  });
}
