// e2e 공용 — 콘솔 오류 모으기, 타일 출처가 다른 UI 에 가리지 않았는지
import { expect, type Browser, type CDPSession, type Page } from "@playwright/test";

export function consoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

/** 배경 타일 서버 오류(외부)만 뺀다 */
export function ownErrors(errors: string[]): string[] {
  return errors.filter((e) => !/tile\.openstreetmap|api\.vworld/i.test(e));
}

/** 보이기만 하는 게 아니라 가리지 않았나 — 링크 왼쪽·가운데·오른쪽 점의 맨 위 요소가 그 링크인지 */
export async function expectAttributionUncovered(page: Page) {
  const name = "© OpenStreetMap contributors";
  const link = page.getByRole("link", { name });
  await expect(link).toBeVisible();
  const box = await link.boundingBox();
  expect(box).not.toBeNull();
  const b = box ?? { x: 0, y: 0, width: 0, height: 0 };
  const y = b.y + b.height / 2;
  for (const x of [b.x + 2, b.x + b.width / 2, b.x + b.width - 2]) {
    const hit = await page.evaluate(
      ([px, py]) => document.elementFromPoint(px ?? 0, py ?? 0)?.closest("a")?.textContent ?? null,
      [x, y],
    );
    expect(hit).toBe(name);
  }
}

/** 하단 시트를 손잡이 탭으로 펼친다(접힘 → 절반, T5.6). 접힌 시트 안의 버튼은 가려져 못 누른다 */
export async function expandSheet(page: Page, name: string) {
  const sheet = page.getByRole("region", { name });
  if ((await sheet.getAttribute("data-stage")) === "collapsed") {
    await sheet.getByRole("button", { name: "시트 높이" }).click();
    await expect(sheet).not.toHaveAttribute("data-stage", "collapsed");
  }
}

/**
 * 이 페이지의 브라우저 컨텍스트에 위치 권한 '거부'를 건다 (T5.7). Playwright 는 허용만 줄 수 있고,
 * 헤드리스 Chrome 은 권한을 안 주면 묻기만 하고 끝나지 않는다 — DevTools Protocol 로 거부한다.
 * 세션을 닫으면(detach) 덮어쓴 권한이 풀리므로 테스트가 끝날 때까지 열어 둔다
 */
export async function denyGeolocation(browser: Browser, page: Page): Promise<CDPSession> {
  const cdp = await browser.newBrowserCDPSession();
  const { targetInfos } = await cdp.send("Target.getTargets");
  const ids = new Set(
    targetInfos
      .filter((t) => t.type === "page" && t.url === page.url())
      .map((t) => t.browserContextId),
  );
  expect(ids.size).toBe(1);
  for (const browserContextId of ids) {
    await cdp.send("Browser.setPermission", {
      permission: { name: "geolocation" },
      setting: "denied",
      browserContextId,
    });
  }
  return cdp;
}
