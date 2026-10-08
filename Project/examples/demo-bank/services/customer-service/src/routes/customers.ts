import { Router, type Request, type Response, type NextFunction } from 'express';
import { z } from 'zod';
import { ProfileService } from '../services/profile-service.js';
import { CustomerRepository, ProfileConflictError } from '../repositories/customer-repository.js';
import { AppDataSource } from '../database.js';

/** The hosting application attaches a principal after validating its access token. */
interface AuthenticatedRequest extends Request {
  principal?: { subject: string; customerId: string; roles: string[] };
}

const router = Router();
const profiles = new ProfileService(new CustomerRepository(AppDataSource));
const customerId = z.string().uuid();
const profilePatch = z.object({
  displayName: z.string().trim().min(2).max(120).optional(),
  email: z.string().email().max(254).optional(),
  phoneNumber: z.string().regex(/^\+[1-9]\d{7,14}$/).optional(),
  version: z.number().int().nonnegative(),
}).strict().refine(body => body.displayName || body.email || body.phoneNumber,
  { message: 'At least one profile field is required' });
const verificationRequest = z.object({
  phoneNumber: z.string().regex(/^\+[1-9]\d{7,14}$/),
  evidenceReference: z.string().uuid(),
}).strict();

function authorize(request: AuthenticatedRequest, staffOnly = false): void {
  const principal = request.principal;
  if (!principal) throw Object.assign(new Error('Authentication required'), { status: 401 });
  const staff = principal.roles.includes('customer_support');
  if ((staffOnly && !staff) || (!staff && principal.customerId !== request.params.id)) {
    throw Object.assign(new Error('Customer access denied'), { status: 403 });
  }
}

router.get('/customers/:id', async (request: AuthenticatedRequest, response, next) => {
  try {
    authorize(request);
    response.json(await profiles.getProfile(customerId.parse(request.params.id)));
  } catch (error) { next(error); }
});

router.put('/customers/:id/profile', async (request: AuthenticatedRequest, response, next) => {
  try {
    authorize(request);
    const body = profilePatch.parse(request.body);
    response.json(await profiles.updateProfile(customerId.parse(request.params.id), body));
  } catch (error) { next(error); }
});

router.post('/customers/:id/phone/verify', async (request: AuthenticatedRequest, response, next) => {
  try {
    authorize(request, true);
    const body = verificationRequest.parse(request.body);
    // Staff first reviews a recorded contact-evidence case in the support system.
    const profile = await profiles.verifyPhone(customerId.parse(request.params.id),
      body.phoneNumber, body.evidenceReference, request.principal!.subject);
    response.json(profile);
  } catch (error) { next(error); }
});

router.use((error: unknown, request: Request, response: Response, next: NextFunction) => {
  if (error instanceof z.ZodError) {
    response.status(400).json({ message: 'Invalid customer request' });
  } else if (error instanceof ProfileConflictError) {
    response.status(409).json({ message: error.message });
  } else if (error instanceof Error && 'status' in error) {
    response.status(Number(error.status)).json({ message: error.message });
  } else {
    next(error);
  }
});

export default router;
