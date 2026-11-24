CREATE TABLE `movement_tags` (
	`movement_id` text NOT NULL,
	`tag` text NOT NULL,
	CONSTRAINT `movement_tags_pk` PRIMARY KEY(`movement_id`, `tag`),
	CONSTRAINT `fk_movement_tags_movement_id_movements_id_fk` FOREIGN KEY (`movement_id`) REFERENCES `movements`(`id`),
	CONSTRAINT `fk_movement_tags_tag_tags_name_fk` FOREIGN KEY (`tag`) REFERENCES `tags`(`name`)
);
--> statement-breakpoint
CREATE TABLE `movements` (
	`seq` integer PRIMARY KEY,
	`id` text NOT NULL UNIQUE,
	`account_id` text NOT NULL,
	`date` text NOT NULL,
	`payee` text NOT NULL,
	`amount` integer NOT NULL,
	`category_id` text,
	`transfer` text,
	`note` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`deleted_at` text,
	CONSTRAINT `fk_movements_account_id_accounts_id_fk` FOREIGN KEY (`account_id`) REFERENCES `accounts`(`id`),
	CONSTRAINT `fk_movements_category_id_categories_id_fk` FOREIGN KEY (`category_id`) REFERENCES `categories`(`id`),
	CONSTRAINT "movements_id" CHECK("id" IS NOT NULL AND length("id") = 4 AND "id" NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'),
	CONSTRAINT "movements_date" CHECK(date("date") IS "date"),
	CONSTRAINT "movements_payee" CHECK(length(trim("payee")) > 0),
	CONSTRAINT "movements_amount" CHECK("amount" <> 0),
	CONSTRAINT "movements_category_or_transfer" CHECK(("category_id" IS NULL) = ("transfer" IS NOT NULL))
);
--> statement-breakpoint
CREATE INDEX `movements_account_date` ON `movements` (`account_id`,`date`,`seq`);