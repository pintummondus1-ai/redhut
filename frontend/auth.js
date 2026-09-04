// Axiom - Auth Injector | Boss Man Fix for UNAUTHORIZED
// fuck yeah, this injects X-Admin-Token into every fetch so original REDHAT JS works with secure backend
(function(){
  const TOKEN_KEY = "admin_token";
  // Try to get token from localStorage, URL ?token=, or default
  let token = localStorage.getItem(TOKEN_KEY) || new URLSearchParams(location.search).get("token") || "change_me_32_chars_strong_secret_12345";
  if(new URLSearchParams(location.search).get("token")){
    localStorage.setItem(TOKEN_KEY, token);
    console.log("[AXIOM] fuck yeah boss man, token saved from URL:", token.slice(0,6)+"***");
  }
  // Prompt if still default and you want custom
  if(!localStorage.getItem(TOKEN_KEY)){
    localStorage.setItem(TOKEN_KEY, token);
  }
  const origFetch = window.fetch;
  window.fetch = function(url, opts={}){
    opts.headers = opts.headers || {};
    // Only inject for same-origin /api calls
    if(typeof url === "string" && url.includes("/api/")){
      if(!opts.headers["X-Admin-Token"] && !opts.headers["x-admin-token"]){
        opts.headers["X-Admin-Token"] = localStorage.getItem(TOKEN_KEY) || token;
      }
    }
    return origFetch(url, opts);
  };
  console.log("[AXIOM] Auth injector active, boss man - token:", (localStorage.getItem(TOKEN_KEY)||token).slice(0,6)+"***", "that's what the hell is going on");
})();
