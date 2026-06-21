// Public API of the design system. Import from "@/ui" anywhere in the app.
//
// This module is app-agnostic by contract (docs/adr/0002): it depends only on
// React, Tailwind, and generic UI libraries — never on app/domain code. An ESLint
// boundary enforces it. See ui/README.md.

export { Badge, badgeVariants } from "./components/badge"

export { Button, buttonVariants } from "./components/button"
export {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "./components/card"
export type { CheckboxProps } from "./components/checkbox"
export { Checkbox } from "./components/checkbox"
export {
  Dialog,
  DialogBackdrop,
  DialogClose,
  DialogDescription,
  DialogPopup,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
} from "./components/dialog"
export {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./components/dropdown-menu"
export { Input } from "./components/input"
export { Label } from "./components/label"
export type { SelectItem, SelectProps } from "./components/select"
export { Select } from "./components/select"
export { Skeleton } from "./components/skeleton"
export { Toaster } from "./components/sonner"
export {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "./components/table"
export {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  tabsListVariants,
} from "./components/tabs"
export { Textarea } from "./components/textarea"
export { cn } from "./lib/cn"
