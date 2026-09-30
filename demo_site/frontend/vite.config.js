import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // 관리자 패널(frontend/)이 3000번을 strictPort로 점유하므로 겹치지 않게 3100번 사용.
    // 시연 중 발표자 노트북에서 관리자 패널과 공격 사이트를 동시에 띄워둘 수 있어야 함.
    port: 3100,
    strictPort: true,
  },
});
