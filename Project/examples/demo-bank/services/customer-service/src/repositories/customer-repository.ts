import { type DataSource } from 'typeorm';
import { Customer } from '../entities/customer.js';

export interface ProfilePatch {
  displayName?: string;
  email?: string;
  phoneNumber?: string;
  version: number;
}

export class ProfileConflictError extends Error {}

/** Transactional writes protect verification state from concurrent profile edits. */
export class CustomerRepository {
  constructor(private readonly database: DataSource) {}

  findById(id: string): Promise<Customer | null> {
    return this.database.getRepository(Customer).findOne({
      where: { id }, relations: { contactPreferences: true },
    });
  }

  async updateProfile(id: string, patch: ProfilePatch): Promise<Customer> {
    await this.database.transaction(async manager => {
      const repository = manager.getRepository(Customer);
      const customer = await repository.findOne({ where: { id }, lock: { mode: 'pessimistic_write' } });
      if (!customer) throw Object.assign(new Error('Customer not found'), { status: 404 });
      if (customer.version !== patch.version) {
        throw new ProfileConflictError('Profile changed; reload before saving');
      }
      if (patch.displayName !== undefined) customer.displayName = patch.displayName;
      if (patch.email !== undefined) customer.email = patch.email;
      if (patch.phoneNumber !== undefined && patch.phoneNumber !== customer.phoneNumber) {
        customer.phoneNumber = patch.phoneNumber;
        customer.phoneVerifiedAt = null;
        customer.phoneVerificationEvidence = null;
        customer.phoneVerifiedBy = null;
      }
      await repository.save(customer);
    });
    return (await this.findById(id))!;
  }

  async verifyPhone(id: string, phone: string, evidence: string, staffSubject: string): Promise<Customer> {
    await this.database.transaction(async manager => {
      const repository = manager.getRepository(Customer);
      const customer = await repository.findOne({ where: { id }, lock: { mode: 'pessimistic_write' } });
      if (!customer) throw Object.assign(new Error('Customer not found'), { status: 404 });
      if (customer.phoneNumber !== phone) {
        throw new ProfileConflictError('Phone number changed during evidence review');
      }
      customer.phoneVerifiedAt = new Date();
      customer.phoneVerificationEvidence = evidence;
      customer.phoneVerifiedBy = staffSubject;
      await repository.save(customer);
    });
    return (await this.findById(id))!;
  }
}
