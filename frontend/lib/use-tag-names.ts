"use client"

import { useQuery } from "@tanstack/react-query"
import { listTags } from "@/lib/api/tags"
import { qk } from "@/lib/query"

export function useTagNames(): string[] {
  const tags = useQuery({ queryKey: qk.tags(), queryFn: () => listTags() })
  return tags.data?.map((tag) => tag.name) ?? []
}
