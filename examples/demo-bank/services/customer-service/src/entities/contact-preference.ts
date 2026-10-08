import { Entity, PrimaryGeneratedColumn, Column, ManyToOne, JoinColumn, type Relation,
  Unique, UpdateDateColumn } from 'typeorm';
import { Customer } from './customer.js';

/** Delivery preferences are separate from the customer's contact addresses. */
@Entity('contact_preferences')
@Unique(['customerId', 'channel', 'purpose'])
export class ContactPreference {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ name: 'customer_id', type: 'uuid' })
  customerId!: string;

  @Column({ type: 'varchar', length: 16 })
  channel!: 'sms' | 'email';

  @Column({ type: 'varchar', length: 24 })
  purpose!: 'marketing' | 'service_updates';

  @Column({ type: 'boolean', default: false })
  enabled!: boolean;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt!: Date;

  @ManyToOne(() => Customer, customer => customer.contactPreferences, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'customer_id' })
  customer!: Relation<Customer>;
}
