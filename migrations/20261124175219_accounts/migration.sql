CREATE TABLE `accounts` (
	`id` text PRIMARY KEY,
	`emoji` text,
	`name` text NOT NULL,
	`type` text NOT NULL,
	`currency` text NOT NULL,
	`archived` integer DEFAULT false NOT NULL,
	`opening_amount` integer DEFAULT 0 NOT NULL,
	`opening_date` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`deleted_at` text,
	CONSTRAINT "accounts_id" CHECK("id" IS NOT NULL AND length("id") = 4 AND "id" NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'),
	CONSTRAINT "accounts_name" CHECK(length(trim("name")) > 0),
	CONSTRAINT "accounts_type" CHECK("type" IN ('savings','debit','credit','cash')),
	CONSTRAINT "accounts_currency" CHECK(length("currency") = 3 AND "currency" NOT GLOB '*[^A-Z]*'),
	CONSTRAINT "accounts_archived" CHECK("archived" IN (0, 1)),
	CONSTRAINT "accounts_opening_date" CHECK("opening_date" IS NULL OR date("opening_date") IS "opening_date"),
	CONSTRAINT "accounts_opening_amount" CHECK("opening_amount" = 0 OR "opening_date" IS NOT NULL)
);
--> statement-breakpoint
CREATE UNIQUE INDEX `accounts_name_unique` ON `accounts` (`name`) WHERE "accounts"."deleted_at" IS NULL;