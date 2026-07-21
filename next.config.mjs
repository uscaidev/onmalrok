/** @type {import('next').NextConfig} */
const nextConfig = {
  // 이 개발 장비(Windows ARM64)에서 SWC 네이티브 바이너리 로드가 실패해 Babel(.babelrc)로
  // 컴파일한다. swcMinify=false는 그 짝(Terser 최소화). SWC가 동작하는 환경이면 둘 다 제거 가능.
  swcMinify: false,
};

export default nextConfig;
