#include "napi/native_api.h"
#include <atomic>
#include <dlfcn.h>
#include <link.h>
#include <pthread.h>
#include <cstdlib>
#include <cstring>
#include <string>

using StringCall = char *(*)();
using FreeCall = void (*)(char *);
struct Work {
    napi_async_work async = nullptr;
    napi_deferred deferred = nullptr;
    std::string mode;
    std::string result;
};
struct Callbacks {
    StringCall hello;
    FreeCall release;
    bool example;
    std::atomic<int> completed{0};
    std::atomic<int> failures{0};
};
static std::atomic<bool> started{false};

static int ExistingGo(dl_phdr_info *info, size_t, void *context) {
    const char *name = info->dlpi_name;
    if (name && (std::strstr(name, "libtailscale_go.so") ||
        std::strstr(name, "libportprobe_core.so") || std::strstr(name, "libohos_example.so"))) {
        *static_cast<bool *>(context) = true;
        return 1;
    }
    return 0;
}

static void *Exercise(void *context) {
    auto *calls = static_cast<Callbacks *>(context);
    for (int i = 0; i < 100; ++i) {
        char *value = calls->hello();
        if (!value || !std::strstr(value, "go1.27.3-ohos-devel") ||
            (calls->example && !std::strstr(value, "openharmony=true"))) {
            calls->failures.fetch_add(1);
        }
        if (value) calls->release(value);
        calls->completed.fetch_add(1);
    }
    return nullptr;
}

static bool Check(StringCall function, FreeCall release, const char *expected, bool prefix = false) {
    if (!function) return false;
    char *value = function();
    bool passed = value && (prefix ? std::strncmp(value, expected, std::strlen(expected)) == 0 :
        std::strcmp(value, expected) == 0);
    if (value) release(value);
    return passed;
}

static std::string RunProbe(const std::string &mode) {
    if (started.exchange(true)) return "{\"passed\":false,\"error\":\"not_cold\"}";
    bool existing = false;
    dl_iterate_phdr(ExistingGo, &existing);
    if (existing) return "{\"passed\":false,\"error\":\"existing_runtime\"}";
    bool example = mode == "go";
    void *library = dlopen(example ? "libohos_example.so" : "libportprobe_core.so", RTLD_NOW | RTLD_LOCAL);
    if (!library) return "{\"passed\":false,\"error\":\"dlopen\"}";
    auto hello = reinterpret_cast<StringCall>(dlsym(library, example ? "OhosHello" : "TSHello"));
    auto release = reinterpret_cast<FreeCall>(dlsym(library, example ? "OhosFree" : "TSFreeString"));
    if (!hello || !release) return "{\"passed\":false,\"error\":\"symbols\"}";
    int exports = 2;
    bool version = true, stopped = true, engine = true, media = true;
    if (!example) {
        const char *names[] = {
#include "exports.inc"
        };
        exports = 0;
        for (const char *name : names) if (dlsym(library, name)) ++exports;
        version = Check(reinterpret_cast<StringCall>(dlsym(library, "TSTailscaleVersion")), release, "1.104.5");
        stopped = Check(reinterpret_cast<StringCall>(dlsym(library, "TSBackendStatus")), release, "STOPPED", true);
        media = Check(reinterpret_cast<StringCall>(dlsym(library, "TSMediaProbeSelfTest")), release,
            "{\"cases\":4,\"state\":\"passed\"}");
        engine = Check(reinterpret_cast<StringCall>(dlsym(library, "TSProbeEngine")), release, "OK | Tailscale 1.104.5", true);
    }
    Callbacks calls{hello, release, example};
    pthread_t threads[4];
    int created = 0;
    for (; created < 4; ++created) if (pthread_create(&threads[created], nullptr, Exercise, &calls)) break;
    for (int i = 0; i < created; ++i) if (pthread_join(threads[i], nullptr)) std::abort();
    bool passed = created == 4 && calls.completed == 400 && calls.failures == 0 &&
        exports == (example ? 2 : 41) && version && stopped && engine && media;
    // Go runtimes remain loaded until the process is force-stopped. Never dlclose.
    return std::string("{\"schema\":1,\"mode\":\"") + mode + "\",\"passed\":" + (passed ? "true" : "false") +
        ",\"exports\":" + std::to_string(exports) + ",\"threads\":" + std::to_string(created) +
        ",\"callbacks\":" + std::to_string(calls.completed.load()) + ",\"failures\":" + std::to_string(calls.failures.load()) +
        ",\"versionMatched\":" + (example ? "null" : (version ? "true" : "false")) + ",\"backendStopped\":" + (example ? "null" : (stopped ? "true" : "false")) +
        ",\"engineInitialized\":" + (example ? "null" : (engine ? "true" : "false")) + ",\"mediaSelfTest\":" + (example ? "null" : (media ? "true" : "false")) + "}";
}

static void Execute(napi_env, void *context) {
    auto *work = static_cast<Work *>(context);
    work->result = RunProbe(work->mode);
}
static void Complete(napi_env env, napi_status status, void *context) {
    auto *work = static_cast<Work *>(context);
    napi_value value = nullptr;
    if (status == napi_ok && napi_create_string_utf8(env, work->result.c_str(), work->result.size(), &value) == napi_ok) {
        napi_resolve_deferred(env, work->deferred, value);
    } else {
        napi_create_string_utf8(env, "probe failed", NAPI_AUTO_LENGTH, &value);
        napi_reject_deferred(env, work->deferred, value);
    }
    napi_delete_async_work(env, work->async);
    delete work;
}
static napi_value Run(napi_env env, napi_callback_info info) {
    size_t argc = 1, size = 0;
    napi_value argument = nullptr;
    char mode[8]{};
    if (napi_get_cb_info(env, info, &argc, &argument, nullptr, nullptr) != napi_ok || argc != 1 ||
        napi_get_value_string_utf8(env, argument, mode, sizeof(mode), &size) != napi_ok ||
        (std::strcmp(mode, "go") && std::strcmp(mode, "core"))) {
        napi_throw_type_error(env, "1", "mode must be go or core"); return nullptr;
    }
    auto *work = new Work();
    work->mode = mode;
    napi_value promise = nullptr, name = nullptr;
    if (napi_create_promise(env, &work->deferred, &promise) != napi_ok ||
        napi_create_string_utf8(env, "PortProbe", NAPI_AUTO_LENGTH, &name) != napi_ok ||
        napi_create_async_work(env, nullptr, name, Execute, Complete, work, &work->async) != napi_ok ||
        napi_queue_async_work(env, work->async) != napi_ok) {
        if (work->async) napi_delete_async_work(env, work->async);
        delete work; napi_throw_error(env, "2", "cannot queue probe"); return nullptr;
    }
    return promise;
}
static napi_value Initialize(napi_env env, napi_value exports) {
    napi_property_descriptor descriptor = {"run", nullptr, Run, nullptr, nullptr, nullptr, napi_default, nullptr};
    napi_define_properties(env, exports, 1, &descriptor);
    return exports;
}
static napi_module module = {1, 0, nullptr, Initialize, "portprobe", nullptr, {nullptr}};
extern "C" __attribute__((constructor)) void RegisterProbe() { napi_module_register(&module); }
