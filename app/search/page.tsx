import { Suspense } from "react";
import SearchClient from "./SearchClient";

export const metadata = { title: "검색" };

export default function SearchPage() {
  return (
    <Suspense>
      <SearchClient />
    </Suspense>
  );
}
