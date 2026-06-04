/**
 * Pure business logic — no I/O here.
 * All functions must be deterministic and testable without mocks.
 */

export function greet(name: string): string {
  if (!name.trim()) throw new Error("name must not be blank");
  return `Hello, ${name}!`;
}
