// 설치된 패키지를 그대로 읽는다 (pnpm install 결과). 기대값은 파일을 열어 확인:
// node_modules/maplibre-gl/package.json 6.16.0 · BSD-3-Clause, LICENSE.txt 1행 "Copyright (c) 2023, MapLibre contributors"·
// 36행 "Copyright (c) 2020, Mapbox". next/license.md · react/LICENSE · react-dom/LICENSE 는 MIT
import { describe, expect, it } from "vitest";
import { runtimeNotices } from "./notices";

describe("오픈소스 고지 (runtimeNotices)", () => {
  const notices = runtimeNotices();

  it("고지 대상 = package.json dependencies (브라우저로 나가는 것), 이름순", () => {
    expect(notices.map((n) => n.name)).toEqual(["maplibre-gl", "next", "react", "react-dom"]);
  });

  it("maplibre-gl 은 BSD-3-Clause 전문 — MapLibre·Mapbox 저작권 고지가 둘 다", () => {
    const m = notices.find((n) => n.name === "maplibre-gl");
    expect(m?.version).toBe("6.16.0");
    expect(m?.license).toBe("BSD-3-Clause");
    expect(m?.text).toContain("Copyright (c) 2023, MapLibre contributors");
    expect(m?.text).toContain("Copyright (c) 2020, Mapbox");
    expect(m?.text).toContain("Redistribution and use in source and binary forms");
  });

  it("next·react·react-dom 은 MIT 전문", () => {
    for (const name of ["next", "react", "react-dom"]) {
      const n = notices.find((x) => x.name === name);
      expect(n?.license).toBe("MIT");
      expect(n?.text).toContain("Permission is hereby granted, free of charge");
    }
  });
});
