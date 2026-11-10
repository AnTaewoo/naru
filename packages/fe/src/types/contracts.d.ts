/* 생성물 — scripts/export_schema.py (naru_contracts). 손으로 고치지 않는다 */

export type From = string;
export type To = string;
export type Via = string[];
export type Segments = SummarySegment[];
export type Points = string[];
export type ReportedPeople = number | null;
export type Roads = string[];
export type ClosureType = "marathon" | "march" | "rally" | "event" | "incident";
export type EvidenceKind = "notice" | "timetable" | "topis_incident" | "bus_skip" | "bus_return" | "rtd_spike";
export type Ref = string;
export type At = string;
export type Detail = {
  [k: string]: number | string;
} | null;
/**
 * 횡단보도 통행을 막는 재료인가 (ADR-008). 파서의 none 은 BE로 오지 않는다.
 */
export type Impact = "blocks" | "unknown";
export type Kind = "line";
/**
 * @minItems 2
 */
export type Coordinates = [[unknown, unknown], [unknown, unknown], ...[unknown, unknown][]];
export type NoticeId = string;
export type SentenceId = string;
export type SourceUrl = string;
export type PublishedAt = string;
export type Excerpt = string;
export type Canonical = string;
export type Lng = number;
export type Lat = number;
export type GazetteerSource = string;
export type GazetteerId = string;
export type Kind1 = "point";
/**
 * @minItems 2
 * @maxItems 2
 */
export type Coordinates1 = [unknown, unknown];
/**
 * 도로명 접미사. BE가 버퍼 폭을 고른다 (대로 25m / 로 15m / 길 8m — naru_be/config.py).
 */
export type RoadClass = "대로" | "로" | "길";
export type Kind2 = "segment";
export type Via1 = PlacePoint[];
export type Road = string | null;
export type Source = "course" | "smpa" | "topis" | "news" | "seoul_press" | "incident" | "bus" | "rtd";
export type Status = "scheduled" | "confirmed" | "released" | "zone_scheduled";
export type Start = string | null;
export type End = string | null;
export type Kind3 = "zone";
export type ZoneName = string;
export type Polygon = [unknown, unknown][][];
export type CandidateId = string;
export type Geometry = PointGeom | LineGeom | SegmentGeom | ZoneGeom;
export type Confidence = number;
/**
 * @minItems 1
 */
export type Evidence1 = [Evidence, ...Evidence[]];
export type Toward = string | null;
export type Approx = boolean;
export type ReviewRequired = boolean;
export type BatchId = string;
export type ProducedAt = string;
export type Producer = string;
export type Candidates = ClosureCandidate[];
export type BatchId1 = string;
export type Accepted = number;
export type ReviewRequired1 = number;
export type CrosswalksUpdated = number;
export type CrosswalkId = string;
export type Confidence1 = number;
export type Reason = string;
export type Evidence2 = Evidence[];
export type Lng1 = number;
export type Lat1 = number;
/**
 * 횡단보도 통행을 막는 재료인가 (ADR-008). 파서의 none 은 BE로 오지 않는다.
 */
export type Impact1 = "blocks" | "unknown";
export type Approx1 = boolean;
export type From1 = string;
export type To1 = string;
export type DepartAt = string;
export type Mode = string;
export type Avoid = string[];
export type CrosswalkId1 = string;
export type Reason1 = string;
export type Until = string | null;
export type Evidence3 = Evidence[];
export type Approx2 = boolean;
export type Type = string;
export type Coordinates2 = [unknown, unknown][];
export type DurationS = number;
export type DistanceM = number;
export type LegKind = "sidewalk" | "crosswalk" | "underpass" | "overpass" | "stairs" | "elevator" | "station";
export type Name = string | null;
export type DistanceM1 = number;
/**
 * @minItems 2
 * @maxItems 2
 */
export type CoordRange = [unknown, unknown];
export type DurationS1 = number;
export type DistanceM2 = number;
export type Legs = Leg[];
export type Avoided1 = Avoided[];
export type ComputedAt = string;
export type Bbox = string;
export type At1 = string;
export type Type1 = "Feature";
export type Geometry1 = PointGeometry | PolygonGeometry;
export type Type2 = "Point";
/**
 * @minItems 2
 * @maxItems 2
 */
export type Coordinates3 = [unknown, unknown];
export type Type3 = "Polygon";
export type Coordinates4 = [unknown, unknown][][];
export type Confidence2 = number;
export type Reason2 = string;
export type CrosswalkId2 = string | null;
export type ZoneName1 = string | null;
export type Evidence4 =
  | {
      [k: string]: unknown;
    }[]
  | null;
/**
 * 횡단보도 통행을 막는 재료인가 (ADR-008). 파서의 none 은 BE로 오지 않는다.
 */
export type Impact2 = "blocks" | "unknown";
export type Approx3 = boolean;
export type Type4 = "FeatureCollection";
export type Features = Feature[];
export type Bbox1 = string | null;
export type At2 = string | null;
export type From2 = string | null;
export type To2 = string | null;
export type Reason3 = string;
export type Crosswalks = number;
/**
 * @minItems 4
 * @maxItems 4
 */
export type Bbox2 = [unknown, unknown, unknown, unknown];
export type Approx4 = boolean;
export type Districts = string[];
export type Id = string;
export type Confidence3 = number;
export type Area = PolygonGeometry | MultiPolygonGeometry | null;
export type Type5 = "MultiPolygon";
export type Coordinates5 = [unknown, unknown][][][];
export type Centroid = [unknown, unknown] | null;
export type TopisIncident = string | null;
export type TopisNotice = string | null;
export type Smpa = string | null;
export type Course = string | null;
export type Events = ClosureEvent[];
/**
 * @minItems 4
 * @maxItems 4
 */
export type Coverage = [unknown, unknown, unknown, unknown];
export type At3 = string;
export type Truncated = boolean;
export type Q = string;
export type Near = string | null;
export type Id1 = string;
export type Name1 = string;
export type Address = string;
/**
 * @minItems 2
 * @maxItems 2
 */
export type Coord = [unknown, unknown];
/**
 * @maxItems 10
 */
export type Places =
  | []
  | [Place]
  | [Place, Place]
  | [Place, Place, Place]
  | [Place, Place, Place, Place]
  | [Place, Place, Place, Place, Place]
  | [Place, Place, Place, Place, Place, Place]
  | [Place, Place, Place, Place, Place, Place, Place]
  | [Place, Place, Place, Place, Place, Place, Place, Place]
  | [Place, Place, Place, Place, Place, Place, Place, Place, Place]
  | [Place, Place, Place, Place, Place, Place, Place, Place, Place, Place];
export type Lat2 = number;
export type Lng2 = number;
export type Label = string | null;
export type RoadAddress = string | null;
export type Address1 = string | null;
export type Code =
  "invalid_query" | "unauthorized" | "not_found" | "no_route" | "out_of_coverage" | "geocode_unavailable" | "internal";
export type Message = string;
export type Field = string | null;

/**
 * docs/INTERFACE.md v0.5 — scripts/export_schema.py 생성물. 수정 금지
 */
export interface NaruContracts {
  CandidateSummary?: CandidateSummary;
  ClosureType?: ClosureType;
  Evidence?: Evidence;
  EvidenceKind?: EvidenceKind;
  Impact?: Impact;
  LineGeom?: LineGeom;
  NoticeRef?: NoticeRef;
  PlacePoint?: PlacePoint;
  PointGeom?: PointGeom;
  RoadClass?: RoadClass;
  SegmentGeom?: SegmentGeom;
  Source?: Source;
  Status?: Status;
  SummarySegment?: SummarySegment;
  Window?: Window;
  ZoneGeom?: ZoneGeom;
  ClosureCandidate?: ClosureCandidate;
  CandidateBatch?: CandidateBatch;
  CandidateBatchResponse?: CandidateBatchResponse;
  ClosureState?: ClosureState;
  RouteQuery?: RouteQuery;
  Avoided?: Avoided;
  Baseline?: Baseline;
  Leg?: Leg;
  LegKind?: LegKind;
  LineString?: LineString;
  RouteResponse?: RouteResponse;
  ClosuresQuery?: ClosuresQuery;
  Feature?: Feature;
  FeatureProperties?: FeatureProperties;
  PointGeometry?: PointGeometry;
  PolygonGeometry?: PolygonGeometry;
  FeatureCollection?: FeatureCollection;
  ClosureEventsQuery?: ClosureEventsQuery;
  ClosureEvent?: ClosureEvent;
  DataAsOf?: DataAsOf;
  MultiPolygonGeometry?: MultiPolygonGeometry;
  ClosureEventsResponse?: ClosureEventsResponse;
  GeocodeSearchQuery?: GeocodeSearchQuery;
  Place?: Place;
  GeocodeSearchResponse?: GeocodeSearchResponse;
  GeocodeReverseQuery?: GeocodeReverseQuery;
  GeocodeReverseResponse?: GeocodeReverseResponse;
  ErrorDetail?: ErrorDetail;
  ErrorBody?: ErrorBody;
  [k: string]: unknown;
}
/**
 * 공지 item 의 구조화 칸 (v0.12, ADR-012). 문장은 없다 — 화면 문장은 FE i18n 이 만든다.
 */
export interface CandidateSummary {
  segments?: Segments;
  points?: Points;
  reported_people?: ReportedPeople;
  roads?: Roads;
}
/**
 * 공지 구간 이름 (v0.12, ADR-012) — 파서 spans 정규 이름 그대로, 좌표가 안 풀려도 남는다.
 */
export interface SummarySegment {
  from_: From;
  to: To;
  via?: Via;
}
export interface Evidence {
  kind: EvidenceKind;
  ref: Ref;
  at: At;
  detail?: Detail;
}
export interface LineGeom {
  kind?: Kind;
  coordinates: Coordinates;
}
export interface NoticeRef {
  notice_id: NoticeId;
  sentence_id: SentenceId;
  source_url: SourceUrl;
  published_at: PublishedAt;
  excerpt: Excerpt;
}
/**
 * 리졸버가 정규형을 좌표로 바꾼 결과. 모델(Claude)이 만든 좌표는 여기 들어올 수 없다.
 */
export interface PlacePoint {
  canonical: Canonical;
  lng: Lng;
  lat: Lat;
  gazetteer_source: GazetteerSource;
  gazetteer_id: GazetteerId;
}
export interface PointGeom {
  kind?: Kind1;
  coordinates: Coordinates1;
}
/**
 * 구간. 선은 BE CrosswalkIndex.from_segment가 도로 그래프 최단경로로 만든다.
 */
export interface SegmentGeom {
  kind?: Kind2;
  from_: PlacePoint;
  to: PlacePoint;
  via?: Via1;
  road?: Road;
  road_class?: RoadClass | null;
}
export interface Window {
  start?: Start;
  end?: End;
}
export interface ZoneGeom {
  kind?: Kind3;
  zone_name: ZoneName;
  polygon: Polygon;
}
export interface ClosureCandidate {
  candidate_id: CandidateId;
  source: Source;
  type: ClosureType;
  status_hint: Status;
  impact: Impact;
  geometry: Geometry;
  window: Window;
  confidence: Confidence;
  evidence: Evidence1;
  notice_ref?: NoticeRef | null;
  toward?: Toward;
  approx?: Approx;
  review_required?: ReviewRequired;
  summary?: CandidateSummary | null;
}
export interface CandidateBatch {
  batch_id: BatchId;
  produced_at: ProducedAt;
  producer: Producer;
  candidates: Candidates;
}
export interface CandidateBatchResponse {
  batch_id: BatchId1;
  accepted: Accepted;
  review_required: ReviewRequired1;
  crosswalks_updated: CrosswalksUpdated;
}
/**
 * 횡단보도 하나의 현재 상태. BE Repository 결과이자 /closures Feature properties.
 */
export interface ClosureState {
  crosswalk_id: CrosswalkId;
  status: Status;
  confidence: Confidence1;
  window: Window;
  reason: Reason;
  evidence: Evidence2;
  lng: Lng1;
  lat: Lat1;
  impact?: Impact1;
  approx?: Approx1;
}
export interface RouteQuery {
  from: From1;
  to: To1;
  depart_at: DepartAt;
  mode?: Mode;
  avoid?: Avoid;
}
export interface Avoided {
  crosswalk_id: CrosswalkId1;
  status: Status;
  reason: Reason1;
  until?: Until;
  evidence: Evidence3;
  approx?: Approx2;
}
export interface Baseline {
  route: LineString;
  duration_s: DurationS;
  distance_m: DistanceM;
}
export interface LineString {
  type?: Type;
  coordinates: Coordinates2;
}
export interface Leg {
  kind: LegKind;
  name?: Name;
  distance_m: DistanceM1;
  coord_range: CoordRange;
}
export interface RouteResponse {
  route: LineString;
  duration_s: DurationS1;
  distance_m: DistanceM2;
  legs: Legs;
  avoided: Avoided1;
  baseline: Baseline;
  computed_at: ComputedAt;
}
export interface ClosuresQuery {
  bbox: Bbox;
  at: At1;
}
export interface Feature {
  type?: Type1;
  geometry: Geometry1;
  properties: FeatureProperties;
}
export interface PointGeometry {
  type?: Type2;
  coordinates: Coordinates3;
}
export interface PolygonGeometry {
  type?: Type3;
  coordinates: Coordinates4;
}
export interface FeatureProperties {
  status: Status;
  confidence: Confidence2;
  window: Window1;
  reason: Reason2;
  crosswalk_id?: CrosswalkId2;
  zone_name?: ZoneName1;
  evidence?: Evidence4;
  impact?: Impact2;
  approx?: Approx3;
}
export interface Window1 {
  [k: string]: string | null;
}
export interface FeatureCollection {
  type?: Type4;
  features: Features;
}
export interface ClosureEventsQuery {
  bbox?: Bbox1;
  at?: At2;
  from?: From2;
  to?: To2;
}
/**
 * 같은 (reason, window) 의 횡단보도 상태 묶음 (§3.1). status 는 응답 at 기준 (v0.14).
 */
export interface ClosureEvent {
  reason: Reason3;
  window: Window;
  crosswalks: Crosswalks;
  bbox: Bbox2;
  approx?: Approx4;
  type?: ClosureType | null;
  source?: Source | null;
  summary?: CandidateSummary | null;
  notice?: NoticeRef | null;
  districts?: Districts;
  id: Id;
  status: Status;
  confidence: Confidence3;
  area?: Area;
  centroid?: Centroid;
}
export interface MultiPolygonGeometry {
  type?: Type5;
  coordinates: Coordinates5;
}
/**
 * 출처별로 저장된 통제의 가장 늦은 근거 시각 (v0.12, ADR-011 C·ADR-012). 없으면 null.
 */
export interface DataAsOf {
  topis_incident: TopisIncident;
  topis_notice: TopisNotice;
  smpa: Smpa;
  course: Course;
}
export interface ClosureEventsResponse {
  events: Events;
  coverage: Coverage;
  data_as_of: DataAsOf;
  at: At3;
  truncated?: Truncated;
}
export interface GeocodeSearchQuery {
  q: Q;
  near?: Near;
}
export interface Place {
  id: Id1;
  name: Name1;
  address: Address;
  coord: Coord;
}
export interface GeocodeSearchResponse {
  places: Places;
}
export interface GeocodeReverseQuery {
  lat: Lat2;
  lng: Lng2;
}
export interface GeocodeReverseResponse {
  label: Label;
  road_address: RoadAddress;
  address: Address1;
}
export interface ErrorDetail {
  code: Code;
  message: Message;
  field?: Field;
}
export interface ErrorBody {
  error: ErrorDetail;
}
