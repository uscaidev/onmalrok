// 이 개발 장비(Windows ARM64)는 SWC 네이티브 .node 로드가 OS 수준에서 거부된다
// (파일·아키텍처는 정상, ERROR_BAD_EXE_FORMAT). Next 14는 "지원 플랫폼"에서 WASM 폴백을
// 시도하지 않으므로, 로더가 @next/swc-wasm-nodejs(설치됨)를 우선 사용하도록 조건 한 줄을 바꾼다.
// NEXT_DISABLE_SWC_WASM=1로 끌 수 있다. SWC 네이티브가 동작하는 환경에서는 이 패치가 불필요하다.
import { readFile, writeFile } from "node:fs/promises";

const target = new URL("../node_modules/next/dist/build/swc/index.js", import.meta.url);
const ORIGINAL =
  "const shouldLoadWasmFallbackFirst = !disableWasmFallback && unsupportedPlatform && useWasmBinary || isWebContainer;";
const PATCHED =
  "const shouldLoadWasmFallbackFirst = !disableWasmFallback; // patched by scripts/patch-swc-wasm.mjs (win-arm64 native load broken)";

try {
  const src = await readFile(target, "utf8");
  if (src.includes(PATCHED)) {
    console.log("patch-swc-wasm: already patched");
  } else if (src.includes(ORIGINAL)) {
    await writeFile(target, src.replace(ORIGINAL, PATCHED));
    console.log("patch-swc-wasm: patched next/dist/build/swc/index.js");
  } else {
    console.warn("patch-swc-wasm: target line not found — next 버전 변경 시 패치 갱신 필요");
  }
} catch (e) {
  console.warn("patch-swc-wasm: skipped:", e.message);
}
