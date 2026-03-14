import type { Context, Next } from "hono";
import * as jose from "jose";

const JWT_SECRET = new TextEncoder().encode(process.env.JWT_SECRET || "change-me-in-production");

export async function authMiddleware(c: Context, next: Next) {
	const authHeader = c.req.header("Authorization");

	if (!authHeader?.startsWith("Bearer ")) {
		return c.json({ error: "Missing or invalid Authorization header" }, 401);
	}

	const token = authHeader.slice(7);

	try {
		const { payload } = await jose.jwtVerify(token, JWT_SECRET);
		c.set("user", payload);
		await next();
	} catch {
		return c.json({ error: "Invalid or expired token" }, 401);
	}
}

export async function createToken(payload: Record<string, unknown>): Promise<string> {
	const expiration = Number(process.env.JWT_EXPIRATION) || 3600;

	return new jose.SignJWT(payload)
		.setProtectedHeader({ alg: "HS256" })
		.setIssuedAt()
		.setExpirationTime(`${expiration}s`)
		.sign(JWT_SECRET);
}
