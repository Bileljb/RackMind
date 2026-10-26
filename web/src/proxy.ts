import { NextResponse, type NextRequest } from "next/server";

// Must match SESSION_COOKIE in api/app/core/security.py.
const SESSION_COOKIE = "rackmind_session";

/**
 * Runs before every page request (Next.js 16 calls this "proxy"; it used to be "middleware").
 *
 * An *optimistic* check only: is there a session cookie at all? If not, send the visitor to
 * the login page instead of rendering a page that would just fail. It can't tell whether the
 * token is valid or expired (that needs the secret, which stays in the API): the API checks
 * every request, and the web app redirects to login when the API answers 401.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();

  const login = new URL("/login", request.url);
  const { pathname, search } = request.nextUrl;
  if (pathname !== "/") login.searchParams.set("next", pathname + search);
  return NextResponse.redirect(login);
}

export const config = {
  // Every page except the login page itself, the API proxy (/api, it has its own checks),
  // Next.js internals and static files.
  matcher: ["/((?!login|api|_next/static|_next/image|favicon.ico).*)"],
};
