CREATE TABLE `rates` (
	`currency` text PRIMARY KEY,
	`rate` integer NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	CONSTRAINT "rates_currency" CHECK(length("currency") = 3 AND "currency" NOT GLOB '*[^A-Z]*' AND "currency" <> 'COP'),
	CONSTRAINT "rates_rate" CHECK("rate" > 0)
);
