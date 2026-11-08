// (server) 오픈소스·데이터 고지 — 빌드 때 한 번 만든다. 지도 출처 칸·푸터에서 온다 (태우 2026-11-08)
import Link from "next/link";
import { runtimeNotices } from "./notices";
import styles from "./page.module.css";

export const dynamic = "force-static";
export const metadata = { title: "오픈소스·데이터 고지 — 나루" };

/** data/MANIFEST.md 의 출처·라이선스 그대로 */
const DATA_SOURCES: readonly { name: string; license: string }[] = [
  {
    name: "서울 열린데이터광장 — 자치구별 도보 네트워크(OA-21208)·대로변 횡단보도(OA-21209)·육교(OA-21210)·지하철 출입구 리프트(OA-21211)·지하철역 엘리베이터(OA-21212)·지하철역 연계 지하도(OA-21213) 공간정보",
    license: "공공누리 제1유형 (출처표시)",
  },
  {
    name: "서울시 교차로 및 횡단보도 시설·위치정보 (OA-23081)",
    license: "공공누리 제1유형 (출처표시)",
  },
  { name: "국토교통부 표준노드링크 (공공데이터포털)", license: "이용허락범위 제한 없음" },
  {
    name: "2026 서울마라톤 구간별 교통 통제·해제 시간 — 서울시 '내 손안에 서울' 기사·교통통제 안내 포스터",
    license: "공공누리 제4유형 (출처표시·상업적 이용 금지·변경 금지)",
  },
  { name: "서울경찰청 '오늘의 주요집회'", license: "경찰청 공개 게시물" },
  {
    name: "서울 교통정보시스템(TOPIS) 공지사항 (OA-22861)",
    license: "공공누리 제2유형 (출처표시·상업적 이용 금지)",
  },
  { name: "TOPIS 실시간 돌발·링크 정보 (OA-13310~13315)", license: "공공누리 제1유형 (출처표시)" },
  {
    name: "지명 좌표 — 카카오 로컬 API 검색 결과 (서비스 안 캐시로 기록·재생)",
    license: "카카오 API 이용약관",
  },
];

export default function LicensesPage() {
  const notices = runtimeNotices();
  return (
    <main className={styles.page}>
      <p>
        <Link href="/">← 지도로</Link>
      </p>
      <h1>오픈소스·데이터 고지</h1>

      <section aria-labelledby="tiles">
        <h2 id="tiles">배경 지도</h2>
        <p>
          지도 데이터{" "}
          <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a> — Open
          Database License(ODbL). VWorld 키가 설정되면 배경 지도는 VWorld(국토교통부)다.
        </p>
      </section>

      <section aria-labelledby="data">
        <h2 id="data">데이터</h2>
        <ul className={styles.data}>
          {DATA_SOURCES.map((d) => (
            <li key={d.name}>
              {d.name} <span className={styles.lic}>{d.license}</span>
            </li>
          ))}
        </ul>
        <p className={styles.note}>
          공지 문장마다 원문 주소(source_url)·게시 시각을 근거로 남긴다. 공지 해석은 Claude API
          응답을 기록해 두고 재생한다.
        </p>
      </section>

      <section aria-labelledby="oss">
        <h2 id="oss">오픈소스 소프트웨어</h2>
        <p className={styles.note}>브라우저로 내려가는 패키지와 그 라이선스 전문.</p>
        {notices.map((n) => (
          <article key={n.name} aria-labelledby={`oss-${n.name}`} className={styles.pkg}>
            <h3 id={`oss-${n.name}`}>
              {n.name} {n.version} · {n.license}
            </h3>
            <pre className={styles.text}>{n.text}</pre>
          </article>
        ))}
      </section>
    </main>
  );
}
