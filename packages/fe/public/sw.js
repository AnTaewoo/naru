// 나루 서비스워커 (ADR-014 C, T7.7·T7.9) — 할 일은 알림뿐. 캐시·오프라인은 하지 않는다(fetch 핸들러 없음).
// push 본문(BE push_dispatcher.payload_of): { kind: created|confirmed, event_id, type, event(사건 이름 첫 줄),
// start, end, url }. 한국어 문구는 여기서 붙인다(BE 는 한국어를 안 만든다). 누르면 그 사건 카드로.

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

const KIND_KO = { created: "통제 예정", confirmed: "통제 시작" };
const TYPE_KO = { marathon: "마라톤", march: "행진", rally: "집회", event: "행사" };

function payloadOf(event) {
  try {
    const data = event.data ? event.data.json() : {};
    return typeof data === "object" && data !== null ? data : {};
  } catch {
    return { event: event.data ? event.data.text() : "" };
  }
}

function hhmm(iso) {
  if (typeof iso !== "string") return "";
  const m = /T(\d{2}):(\d{2})/.exec(iso);
  return m ? `${m[1]}:${m[2]}` : "";
}

self.addEventListener("push", (event) => {
  const data = payloadOf(event);
  const kind = KIND_KO[data.kind] || "통제 알림";
  const type = TYPE_KO[data.type] ? ` · ${TYPE_KO[data.type]}` : "";
  const when = hhmm(data.start)
    ? `${hhmm(data.start)}${hhmm(data.end) ? `–${hhmm(data.end)}` : ""} · `
    : "";
  const options = {
    body: `${when}${typeof data.event === "string" ? data.event : ""}`,
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-192.png",
    tag: typeof data.event_id === "string" ? `${data.event_id}:${data.kind || ""}` : undefined,
    data: { url: typeof data.url === "string" ? data.url : "/" },
  };
  event.waitUntil(self.registration.showNotification(`${kind}${type} — 나루`, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url ?? "/", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      const open = list.find((c) => "navigate" in c);
      if (open) return open.navigate(url).then((c) => c?.focus());
      return self.clients.openWindow(url);
    }),
  );
});
