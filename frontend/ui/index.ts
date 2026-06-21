// Public API of the design system. Import from "@/ui" anywhere in the app.
//
// This module is app-agnostic by contract (docs/adr/0002): it depends only on
// React, Tailwind, and generic UI libraries — never on app/domain code. An ESLint
// boundary enforces it. See ui/README.md.

export { cn } from "./lib/cn"

export { Button, buttonVariants } from "./components/button"
export { Badge, badgeVariants } from "./components/badge"
export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
} from "./components/card"
export { Input } from "./components/input"
export { Label } from "./components/label"
export { Skeleton } from "./components/skeleton"
export { Toaster } from "./components/sonner"
export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
} from "./components/table"
export {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  tabsListVariants,
} from "./components/tabs"
export {
  Dialog,
  DialogTrigger,
  DialogClose,
  DialogPortal,
  DialogBackdrop,
  DialogPopup,
  DialogTitle,
  DialogDescription,
} from "./components/dialog"
export { Select } from "./components/select"
export type { SelectItem, SelectProps } from "./components/select"
export { Checkbox } from "./components/checkbox"
export type { CheckboxProps } from "./components/checkbox"
