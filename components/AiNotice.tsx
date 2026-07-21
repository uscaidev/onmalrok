import styles from "./AiNotice.module.css";

// §11 카피 고정. ai_inferred 요소가 있는 패널 하단에 삽입.
export default function AiNotice() {
  return (
    <p className={styles.notice}>
      연결 관계 중 &lsquo;AI 추정&rsquo;은 오류가 있을 수 있습니다. 모든 연결은 원문 구간
      재생으로 직접 확인할 수 있습니다.
    </p>
  );
}
