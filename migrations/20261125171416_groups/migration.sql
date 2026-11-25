CREATE TABLE `groups` (
	`id` text PRIMARY KEY,
	`kind` text NOT NULL,
	`emoji` text NOT NULL,
	`name` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`deleted_at` text,
	CONSTRAINT "groups_id" CHECK("id" IS NOT NULL AND length("id") = 4 AND "id" NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'),
	CONSTRAINT "groups_name" CHECK(length(trim("name")) > 0),
	CONSTRAINT "groups_kind" CHECK("kind" IN ('income','spending','outside'))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `groups_name_unique` ON `groups` (`name`) WHERE "groups"."deleted_at" IS NULL;
--> statement-breakpoint
INSERT INTO `groups` (`id`, `kind`, `emoji`, `name`, `created_at`, `updated_at`) VALUES
	('m0z7', 'income', '💰', 'Income', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('y6v7', 'spending', '🚗', 'Auto & Transport', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('jpnq', 'spending', '💡', 'Bills & Utilities', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('d7gd', 'spending', '🧠', 'Education', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('ex09', 'spending', '🎢', 'Entertainment', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('3asb', 'spending', '🧾', 'Financial', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('1aae', 'spending', '🍽️', 'Food & Dining', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('zyt4', 'spending', '🎁', 'Gifts', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('cx75', 'spending', '⚕️', 'Health & Wellness', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('xwvq', 'spending', '🏠', 'Housing', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('q3rh', 'spending', '🛍️', 'Shopping', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('pjbv', 'spending', '💻', 'Software & AI', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('xgn8', 'spending', '✈️', 'Travel', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
	('7hdg', 'outside', '🔄', 'Transfers & Investments', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
