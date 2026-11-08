import Link from "next/link";
import styles from "./Footer.module.css";

// 출처 표기. 데이터 출처는 data/MANIFEST.md 와 같다. 전문은 /licenses
export function Footer() {
  return (
    <footer className={styles.footer}>
      <span>
        나루 · 서울 열린데이터광장(도보망·횡단보도·돌발) · 국토부 표준노드링크 · 서울경찰청 집회
        공지 · <Link href="/licenses">오픈소스·데이터 고지</Link>
      </span>
    </footer>
  );
}
