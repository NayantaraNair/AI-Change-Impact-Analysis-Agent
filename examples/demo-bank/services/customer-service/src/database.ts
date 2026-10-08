import 'reflect-metadata';
import { DataSource } from 'typeorm';
import { Customer } from './entities/customer.js';
import { ContactPreference } from './entities/contact-preference.js';

/** The hosting process initializes this connection before mounting customer routes. */
function databaseUrl(): string {
  const value = process.env.CUSTOMER_DATABASE_URL;
  if (!value) {
    throw new Error('CUSTOMER_DATABASE_URL is required');
  }
  return value;
}

export const AppDataSource = new DataSource({
  type: 'postgres',
  url: databaseUrl(),
  entities: [Customer, ContactPreference],
  // Schema changes are reviewed as SQL under db/migrations, never inferred at boot.
  synchronize: false,
  logging: false,
  extra: {
    max: 10,
    connectionTimeoutMillis: 3000,
  },
});
