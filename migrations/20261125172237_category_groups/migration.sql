PRAGMA defer_foreign_keys = ON;
--> statement-breakpoint
CREATE TEMP TABLE `old_categories` AS SELECT * FROM `categories`;
--> statement-breakpoint
DROP TABLE `categories`;
--> statement-breakpoint
CREATE TABLE `categories` (
	`id` text PRIMARY KEY,
	`emoji` text,
	`name` text NOT NULL,
	`archived` integer DEFAULT false NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`deleted_at` text,
	`group_id` text NOT NULL,
	CONSTRAINT `fk_categories_group_id_groups_id_fk` FOREIGN KEY (`group_id`) REFERENCES `groups`(`id`),
	CONSTRAINT "categories_id" CHECK("id" IS NOT NULL AND length("id") = 4 AND "id" NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'),
	CONSTRAINT "categories_name" CHECK(length(trim("name")) > 0),
	CONSTRAINT "categories_archived" CHECK("archived" IN (0, 1))
);
--> statement-breakpoint
INSERT INTO `categories` (`id`, `emoji`, `name`, `archived`, `created_at`, `updated_at`, `deleted_at`, `group_id`)
	SELECT `id`, `emoji`, `name`, `archived`, `created_at`, `updated_at`, `deleted_at`, CASE `name`
		WHEN 'Rent' THEN 'xwvq'
		WHEN 'Home Maintenance' THEN 'xwvq'
		WHEN 'Laundry' THEN 'xwvq'
		WHEN 'Utilities' THEN 'jpnq'
		WHEN 'Services' THEN 'jpnq'
		WHEN 'Internet' THEN 'jpnq'
		WHEN 'Phone' THEN 'jpnq'
		WHEN 'Restaurants' THEN '1aae'
		WHEN 'Groceries' THEN '1aae'
		WHEN 'Food Delivery' THEN '1aae'
		WHEN 'Coffee Shops' THEN '1aae'
		WHEN 'Food' THEN '1aae'
		WHEN 'Gas' THEN 'y6v7'
		WHEN 'Parking' THEN 'y6v7'
		WHEN 'Tolls' THEN 'y6v7'
		WHEN 'Car Wash' THEN 'y6v7'
		WHEN 'Car Maintenance' THEN 'y6v7'
		WHEN 'Auto Insurance' THEN 'y6v7'
		WHEN 'Rideshare/Taxi' THEN 'y6v7'
		WHEN 'Car Payment' THEN 'y6v7'
		WHEN 'Clothing' THEN 'q3rh'
		WHEN 'Gadgets' THEN 'q3rh'
		WHEN 'Home Goods' THEN 'q3rh'
		WHEN 'Pets' THEN 'q3rh'
		WHEN 'Healthcare' THEN 'cx75'
		WHEN 'Fitness' THEN 'cx75'
		WHEN 'Beauty & Wellness' THEN 'cx75'
		WHEN 'Entertainment' THEN 'ex09'
		WHEN 'Streaming' THEN 'ex09'
		WHEN 'Fun' THEN 'ex09'
		WHEN 'Flights' THEN 'xgn8'
		WHEN 'Car Rental' THEN 'xgn8'
		WHEN 'Lodging' THEN 'xgn8'
		WHEN 'AI Tools' THEN 'pjbv'
		WHEN 'Software' THEN 'pjbv'
		WHEN 'Courses / Learning' THEN 'd7gd'
		WHEN 'Gifts' THEN 'zyt4'
		WHEN 'Taxes' THEN '3asb'
		WHEN 'Accountant' THEN '3asb'
		WHEN 'Bank Fees' THEN '3asb'
		WHEN 'Refund' THEN '3asb'
		WHEN 'Reimbursable' THEN '3asb'
		WHEN 'Salary' THEN 'm0z7'
		WHEN 'Bonuses' THEN 'm0z7'
		WHEN 'Interest' THEN 'm0z7'
		WHEN 'Cashback' THEN 'm0z7'
		WHEN 'Payment / Transfer' THEN '7hdg'
		WHEN 'Investment' THEN '7hdg'
		WHEN 'Investment Gains' THEN '7hdg'
	END FROM `old_categories`;
--> statement-breakpoint
DROP TABLE `old_categories`;
--> statement-breakpoint
CREATE UNIQUE INDEX `categories_name_unique` ON `categories` (`name`) WHERE "categories"."archived" = 0 AND "categories"."deleted_at" IS NULL;