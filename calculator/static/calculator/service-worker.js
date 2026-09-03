const CACHE_NAME = "adevs-cgpa-v4";

const OFFLINE_URL = "/offline/";


// =====================================================
// BASIC APP FILES TO CACHE
// =====================================================

const APP_SHELL = [

    OFFLINE_URL,

    "/login/",

    "/static/calculator/manifest.json",

    "/static/calculator/icons/icon-192.png",

    "/static/calculator/icons/icon-512.png"

];


// =====================================================
// INSTALL
// =====================================================

self.addEventListener(
    "install",
    event => {

        event.waitUntil(

            caches
                .open(CACHE_NAME)

                .then(cache => {

                    console.log(
                        "Caching A-DEVS CGPA app shell"
                    );

                    return cache.addAll(
                        APP_SHELL
                    );

                })

        );

        self.skipWaiting();

    }
);


// =====================================================
// ACTIVATE
// =====================================================

self.addEventListener(
    "activate",
    event => {

        event.waitUntil(

            caches
                .keys()

                .then(cacheNames => {

                    return Promise.all(

                        cacheNames.map(
                            cacheName => {

                                if (
                                    cacheName !==
                                    CACHE_NAME
                                ) {

                                    return caches.delete(
                                        cacheName
                                    );

                                }

                            }
                        )

                    );

                })

        );

        self.clients.claim();

    }
);


// =====================================================
// FETCH
// =====================================================

self.addEventListener(
    "fetch",
    event => {

        const request =
            event.request;


        // Only cache GET requests

        if (
            request.method !== "GET"
        ) {

            return;

        }


        // Only handle http/https

        if (
            !request.url.startsWith("http")
        ) {

            return;

        }


        // =================================================
        // PAGE NAVIGATION
        // =================================================

        if (
            request.mode === "navigate"
        ) {

            event.respondWith(

                fetch(request)

                    .then(response => {

                        // Only cache successful responses

                        if (
                            response &&
                            response.status === 200
                        ) {

                            const copy =
                                response.clone();


                            caches
                                .open(CACHE_NAME)

                                .then(cache => {

                                    cache.put(
                                        request,
                                        copy
                                    );

                                });

                        }


                        return response;

                    })


                    .catch(async () => {

                        // First try the exact page

                        const cachedPage =
                            await caches.match(
                                request
                            );


                        if (cachedPage) {

                            return cachedPage;

                        }


                        // Otherwise show offline page

                        return caches.match(
                            OFFLINE_URL
                        );

                    })

            );


            return;

        }


        // =================================================
        // STATIC FILES
        // =================================================

        event.respondWith(

            caches.match(request)

                .then(cachedResponse => {

                    if (cachedResponse) {

                        return cachedResponse;

                    }


                    return fetch(request)

                        .then(response => {

                            if (
                                !response ||
                                response.status !== 200
                            ) {

                                return response;

                            }


                            const copy =
                                response.clone();


                            caches
                                .open(CACHE_NAME)

                                .then(cache => {

                                    cache.put(
                                        request,
                                        copy
                                    );

                                });


                            return response;

                        });

                })

        );

    }
);