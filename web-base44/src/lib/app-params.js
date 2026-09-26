import { getAccessToken } from '@base44/sdk';

const isNode = typeof window === 'undefined';

const isClearAccessTokenRequested = () =>
	!isNode && new URLSearchParams(window.location.search).get("clear_access_token") === 'true';

const clearStoredAccessToken = () => {
	window.localStorage.removeItem('base44_access_token');
	window.localStorage.removeItem('token');
}

const getAppParams = () => {
	if (isClearAccessTokenRequested()) {
		clearStoredAccessToken();
	}
	return {
		appId: import.meta.env.VITE_BASE44_APP_ID,
		token: getAccessToken(),
		functionsVersion: import.meta.env.VITE_BASE44_FUNCTIONS_VERSION,
		appBaseUrl: import.meta.env.VITE_BASE44_APP_BASE_URL,
		// `npm run dev` on its own has no Base44 backend: the Vite plugin only
		// proxies /api when VITE_BASE44_APP_BASE_URL is set, which `base44 dev`
		// does for you. Without it every Base44 request would 404.
		hasBackend: !import.meta.env.DEV || Boolean(import.meta.env.VITE_BASE44_APP_BASE_URL),
	}
}


export const appParams = {
	...getAppParams()
}
