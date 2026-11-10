// 나루 서비스워커 (ADR-014 C, T7.7) — 할 일은 알림뿐. 캐시·오프라인은 하지 않는다(fetch 핸들러 없음).
// push 를 받으면 늘 showNotification, 누르면 그 사건 카드(/?event=<id>&t=<시작>). 본문은 T7.9 발송이 정한다:
// { title, body, url, tag }

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

function payloadOf(event) {
  try {
    const data = event.data ? event.data.json() : {};
    return typeof data === "object" && data !== null ? data : {};
  } catch {
    return { body: event.data ? event.data.text() : "" };
  }
}

self.addEventListener("push", (event) => {
  const data = payloadOf(event);
  const title = typeof data.title === "string" ? data.title : "나루 — 통제 알림";
  const options = {
    body: typeof data.body === "string" ? data.body : "",
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-192.png",
    tag: typeof data.tag === "string" ? data.tag : undefined,
    data: { url: typeof data.url === "string" ? data.url : "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
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
