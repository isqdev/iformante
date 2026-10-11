import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
const pdf = path.join(process.cwd(), "tests/fixtures/viewer.pdf");
const citations = [
  {
    chunk_id: "chunk1",
    anchors: [{ page: 1, x: 0.1, y: 0.12, width: 0.6, height: 0.03 }],
  },
  {
    chunk_id: "chunk2",
    anchors: [{ page: 3, x: 0.1, y: 0.12, width: 0.6, height: 0.03 }],
  },
];
async function fixtures(page: Page, role: "guest" | "COMMON" | "ADMIN") {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/content"))
      return route.fulfill({ path: pdf, contentType: "application/pdf" });
    if (url.pathname === "/api/auth/me")
      return route.fulfill({
        json:
          role === "guest"
            ? null
            : { id: "testuser1", first_name: "Teste", role },
      });
    if (url.pathname.includes("reset/validate"))
      return route.fulfill({ json: { masked_email: "••••••245" } });
    if (url.pathname === "/api/conversations")
      return route.fulfill({ json: [] });
    if (url.pathname.startsWith("/api/conversations/"))
      return route.fulfill({
        json: {
          id: "chat12345",
          title: "Histórico",
          messages: [
            {
              id: "message01",
              role: "assistant",
              content: "Histórico preservado.",
            },
          ],
        },
      });
    if (url.pathname === "/api/documents")
      return route.fulfill({
        json: [
          {
            id: "doc123456",
            name: "Documento de teste com título longo para verificar a responsividade",
            source_type: "PDF",
            url: null,
            ...(role === "ADMIN"
              ? { status: "INDEXED", uploaded_by_name: "Teste" }
              : {}),
          },
        ],
      });
    if (url.pathname === "/api/documents/metadata")
      return route.fulfill({ json: { title: "Página do IFPR" } });
    if (url.pathname === "/api/chat") {
      const data = `${role === "guest" ? "" : 'event: conversation\ndata: {"conversation_id":"chat12345","title":"Teste"}\n\n'}event: delta\ndata: {"content":"Consulte o documento."}\n\nevent: done\ndata: ${JSON.stringify({ sources: [{ document_id: "doc123456", filename: "Documento.pdf", source_type: "PDF", url: null, citations }] })}\n\n`;
      return route.fulfill({ contentType: "text/event-stream", body: data });
    }
    return route.fulfill({ json: { message: "Solicitação recebida." } });
  });
}
async function noHorizontalOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
}

for (const role of ["COMMON", "ADMIN"] as const) {
  test(`abrir histórico após carregar sessão ${role}`, async ({ page }) => {
    await fixtures(page, role);
    await page.goto("/c/chat12345");
    await expect(page.getByText("Histórico preservado.")).toBeVisible();
  });
}
test("visitante volta ao chat temporário ao abrir histórico privado", async ({
  page,
}) => {
  await fixtures(page, "guest");
  await page.goto("/c/chat12345");
  await expect(page).toHaveURL("/");
  await expect(page.getByText("Histórico preservado.")).toHaveCount(0);
});
for (const width of [320, 390, 768, 1440]) {
  test(`telas de conta responsivas em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 820 });
    await fixtures(page, "ADMIN");
    for (const route of [
      "/",
      "/login",
      "/cadastro",
      "/cadastro/confirmar?registration=123",
      "/recuperar-senha",
      "/recuperar-senha/redefinir?token=token",
      "/conta/alterar-senha",
      "/docs",
    ]) {
      await page.goto(route);
      await expect(
        page.locator("main, [data-slot=sidebar-inset]").first(),
      ).toBeVisible();
      await noHorizontalOverflow(page);
      await page.screenshot({
        path: `test-results/screens/${width}-${route.split("?")[0].replaceAll("/", "_") || "home"}.png`,
        fullPage: true,
        animations: "disabled",
      });
    }
  });
  for (const role of ["guest", "COMMON", "ADMIN"] as const) {
    test(`documentos e PDF para ${role} em ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 820 });
      await fixtures(page, role);
      await page.goto("/docs");
      await expect(
        page.getByText(
          "Documento de teste com título longo para verificar a responsividade",
        ),
      ).toBeVisible();
      if (role !== "ADMIN") {
        await expect(page.getByText("Adicionado por")).toHaveCount(0);
        await expect(page.getByLabel(/^Ações para/)).toHaveCount(0);
      }
      await page
        .getByText(
          "Documento de teste com título longo para verificar a responsividade",
        )
        .click();
      await expect(page).toHaveURL(/\?document=doc123456/);
      await expect(page.getByLabel("Página atual")).toBeVisible();
      const dialog = page.getByRole("dialog");
      const box = await dialog.boundingBox();
      expect(box?.width).toBe(width);
      expect(box?.height).toBe(820);
      await expect(page.getByLabel("Ver citações")).toHaveCount(0);
      await page.getByLabel("Página atual").fill("3");
      await page.getByLabel("Página atual").press("Enter");
      await expect(page.getByLabel("Página atual")).toHaveValue("3");
      await expect
        .poll(() =>
          page
            .locator('[data-pdf-page="3"]')
            .evaluate((el) => el.getBoundingClientRect().top),
        )
        .toBeLessThan(600);
      await noHorizontalOverflow(page);
      await page.screenshot({
        path: `test-results/screens/${width}-${role}-pdf.png`,
        animations: "disabled",
      });
      await page.getByLabel("Fechar visualizador").click();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await page.goBack();
      await expect(page.getByRole("dialog")).toBeVisible();
    });
  }
}
test("autocomplete no login e cadastro", async ({ page }) => {
  await fixtures(page, "guest");
  for (const route of ["/login", "/cadastro"]) {
    await page.goto(route);
    const email = page.getByLabel("E-mail institucional");
    await email.fill("123@");
    await expect(email).toHaveValue("123@estudantes.ifpr.edu.br");
    await email.fill("abc@");
    await expect(email).toHaveValue("abc@ifpr.edu.br");
    await email.fill("ab@");
    await expect(email).toHaveValue("ab@");
    await email.fill("abc@estudantes.ifpr.edu.br");
    await expect(email).toHaveValue("abc@estudantes.ifpr.edu.br");
  }
});
for (const role of ["guest", "COMMON", "ADMIN"] as const) {
  test(`chat e citações para ${role}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await fixtures(page, role);
    await page.goto("/");
    if (role !== "guest")
      await expect(
        page.getByRole("button", { name: "TE Teste", exact: true }),
      ).toBeVisible();
    const input = page.locator("textarea");
    await input.fill("Olá");
    await input.press("Enter");
    await expect(page.getByText("Consulte o documento.")).toBeVisible();
    await page.getByText("Documento.pdf").click();
    await expect(page.getByLabel("Ver citações")).toBeVisible();
    await page.getByLabel("Ver citações").click();
    await expect(page.getByText("1 / 2 citações")).toBeVisible();
    await page.getByLabel("Próxima citação").click();
    await expect(page.getByText("2 / 2 citações")).toBeVisible();
    await page.getByLabel("Ver em tela cheia").click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("2 / 2 citações")).toBeVisible();
    await page.getByLabel("Voltar ao painel lateral").click();
    await page.getByLabel("Configurações do PDF").click();
    await expect(page.getByLabel("Página atual")).toBeVisible();
    await page.setViewportSize({ width: 390, height: 820 });
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByLabel("Página atual")).toBeVisible();
    await expect
      .poll(() =>
        page
          .locator("canvas")
          .first()
          .evaluate((c) => (c as HTMLCanvasElement).width),
      )
      .toBeGreaterThan(0);
    await noHorizontalOverflow(page);
    await page.screenshot({
      path: `test-results/screens/${role}-chat-mobile.png`,
    });
  });
}

for (const width of [320, 390, 768, 1440]) {
  test(`perfil e upload administrativo em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 820 });
    await fixtures(page, "ADMIN");
    await page.goto("/");
    if (width < 768) await page.getByLabel("Abrir menu lateral").click();
    await page.getByRole("button", { name: "TE Teste", exact: true }).click();
    await expect(page.getByText("Admin", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Nome", { exact: true })).toHaveValue("Teste");
    await noHorizontalOverflow(page);
    await page.screenshot({
      path: `test-results/screens/${width}-profile.png`,
    });
    await page.keyboard.press("Escape");
    await page.evaluate(() => {
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(
        new File(["%PDF-test"], "documento.pdf", { type: "application/pdf" }),
      );
      window.dispatchEvent(new DragEvent("dragenter", { dataTransfer }));
    });
    await expect(page.getByText("Solte aqui sua fonte")).toBeVisible();
    await page.evaluate(() => {
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(
        new File(["%PDF-test"], "documento.pdf", { type: "application/pdf" }),
      );
      window.dispatchEvent(new DragEvent("drop", { dataTransfer }));
    });
    await expect(page.getByLabel("Título", { exact: true })).toHaveValue(
      "documento",
    );
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Nova fonte" }),
    ).toBeVisible();
    await noHorizontalOverflow(page);
    await page.screenshot({
      path: `test-results/screens/${width}-upload.png`,
      animations: "disabled",
    });
    await page.keyboard.press("Escape");
    await page.evaluate(() => {
      const dataTransfer = new DataTransfer();
      dataTransfer.setData("text/uri-list", "https://ifpr.edu.br/noticias");
      window.dispatchEvent(new DragEvent("dragenter", { dataTransfer }));
      window.dispatchEvent(new DragEvent("drop", { dataTransfer }));
    });
    await expect(page.getByLabel("Link da página")).toHaveValue(
      "https://ifpr.edu.br/noticias",
    );
    await expect(page.getByLabel("Título (opcional)")).toHaveValue(
      "Página do IFPR",
    );
    await noHorizontalOverflow(page);
  });
}
