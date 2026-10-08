import { Entity, PrimaryGeneratedColumn, Column, OneToMany, VersionColumn,
  CreateDateColumn, UpdateDateColumn } from 'typeorm';
import { ContactPreference } from './contact-preference.js';

/** Profile data belongs to customer-service; authentication owns credentials. */
@Entity('customers')
export class Customer {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ name: 'user_id', type: 'varchar', length: 36, unique: true })
  userId!: string;

  @Column({ name: 'display_name', type: 'varchar', length: 120 })
  displayName!: string;

  @Column({ type: 'varchar', length: 254 })
  email!: string;

  @Column({ name: 'phone_number', type: 'varchar', length: 16, nullable: true })
  phoneNumber!: string | null;

  @Column({ name: 'phone_verified_at', type: 'timestamptz', nullable: true })
  phoneVerifiedAt!: Date | null;

  @Column({ name: 'phone_verification_evidence', type: 'uuid', nullable: true })
  phoneVerificationEvidence!: string | null;

  @Column({ name: 'phone_verified_by', type: 'varchar', length: 120, nullable: true })
  phoneVerifiedBy!: string | null;

  @VersionColumn({ default: 1 })
  version!: number;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt!: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt!: Date;

  @OneToMany(() => ContactPreference, preference => preference.customer)
  contactPreferences!: ContactPreference[];
}
