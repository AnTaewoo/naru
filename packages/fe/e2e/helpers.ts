// e2e 공용 — 콘솔 오류 모으기, 타일 출처가 다른 UI 에 가리지 않았는지
import { expect, type Page } from "@playwright/test";

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
