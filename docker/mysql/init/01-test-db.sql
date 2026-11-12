-- 테스트 전용 DB. 테스트는 트랜잭션 롤백으로 정리한다 (CONVENTIONS §4.3)
CREATE DATABASE IF NOT EXISTS naru_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
GRANT ALL PRIVILEGES ON naru_test.* TO 'naru'@'%';
