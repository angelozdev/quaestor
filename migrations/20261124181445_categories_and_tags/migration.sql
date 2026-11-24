CREATE TABLE `categories` (
	`id` text PRIMARY KEY,
	`emoji` text,
	`name` text NOT NULL,
	`archived` integer DEFAULT false NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`deleted_at` text,
	CONSTRAINT "categories_id" CHECK("id" IS NOT NULL AND length("id") = 4 AND "id" NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'),
	CONSTRAINT "categories_name" CHECK(length(trim("name")) > 0),
	CONSTRAINT "categories_archived" CHECK("archived" IN (0, 1))
);
--> statement-breakpoint
CREATE TABLE `tags` (
	`name` text PRIMARY KEY,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`deleted_at` text,
	CONSTRAINT "tags_name" CHECK("name" IS NOT NULL AND length("name") > 0 AND "name" NOT GLOB '*[^a-z0-9:-]*')
);
--> statement-breakpoint
CREATE UNIQUE INDEX `categories_name_unique` ON `categories` (`name`) WHERE "categories"."archived" = 0 AND "categories"."deleted_at" IS NULL;