import { CustomerRepository, type ProfilePatch } from '../repositories/customer-repository.js';
import type { Customer } from '../entities/customer.js';

/** Owns profile rules; controllers never expose persistence entities directly. */
export class ProfileService {
  constructor(private readonly customers: CustomerRepository) {}

  async getProfile(id: string) {
    const customer = await this.customers.findById(id);
    if (!customer) {
      throw Object.assign(new Error('Customer not found'), { status: 404 });
    }
    return this.toProfile(customer);
  }

  async updateProfile(id: string, patch: ProfilePatch) {
    const normalized = {
      ...patch,
      email: patch.email?.trim().toLowerCase(),
      displayName: patch.displayName?.trim(),
    };
    const customer = await this.customers.updateProfile(id, normalized);
    return this.toProfile(customer);
  }

  async verifyPhone(id: string, phone: string, evidence: string, staffSubject: string) {
    const customer = await this.customers.verifyPhone(id, phone, evidence, staffSubject);
    return this.toProfile(customer);
  }

  private toProfile(customer: Customer) {
    return {
      id: customer.id,
      displayName: customer.displayName,
      email: customer.email,
      phoneNumber: customer.phoneNumber,
      phoneVerified: customer.phoneVerifiedAt !== null,
      version: customer.version,
      contactPreferences: (customer.contactPreferences ?? []).map(preference => ({
        channel: preference.channel,
        purpose: preference.purpose,
        enabled: preference.enabled,
      })),
    };
  }
}
