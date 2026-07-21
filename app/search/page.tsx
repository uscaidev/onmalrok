import { Suspense } from "react";
import SiteHeader from "@/components/SiteHeader";
import SearchClient from "./SearchClient";

export const metadata = { title: "검색" };

export default function SearchPage({ searchParams }: { searchParams: { q?: string } }) {
  const query = searchParams.q ?? "";
  return (
    <>
      <SiteHeader query={query} />
      <Suspense>
        <SearchClient />
      </Suspense>
    </>
  );
}
