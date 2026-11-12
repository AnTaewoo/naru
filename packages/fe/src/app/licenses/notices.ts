// 오픈소스 고지 — package.json dependencies(브라우저로 나가는 런타임 의존성)마다 설치된 패키지의
// 버전·라이선스와 라이선스 파일 전문을 그대로 읽는다. 서버에서만, 빌드 때 (page.tsx 는 force-static)
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

export interface Notice {
  name: string;
  version: string;
  license: string;
  /** 라이선스 파일 전문 (저작권 고지 포함) */
  text: string;
}

interface PackageJson {
  version?: string;
  license?: string;
  dependencies?: Record<string, string>;
}

const LICENSE_FILES = ["LICENSE.txt", "LICENSE", "LICENSE.md", "license.md", "license"];

function readJson(file: string): PackageJson {
  return JSON.parse(readFileSync(file, "utf-8")) as PackageJson;
}

export function readNotice(name: string, root: string = process.cwd()): Notice {
  const dir = path.join(root, "node_modules", name);
  const pkg = readJson(path.join(dir, "package.json"));
  const file = LICENSE_FILES.map((f) => path.join(dir, f)).find((f) => existsSync(f));
  if (!file) throw new Error(`${name}: 라이선스 파일이 없다`);
  return {
    name,
    version: pkg.version ?? "",
    license: pkg.license ?? "",
    text: readFileSync(file, "utf-8").trim(),
  };
}

/** root = packages/fe (next build·dev·vitest 모두 여기서 돈다) */
export function runtimeNotices(root: string = process.cwd()): Notice[] {
  const deps = Object.keys(readJson(path.join(root, "package.json")).dependencies ?? {}).sort();
  return deps.map((name) => readNotice(name, root));
}
