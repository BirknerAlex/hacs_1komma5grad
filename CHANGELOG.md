## [1.2.0](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.1.0...v1.2.0) (2025-05-04)

### 🛠️ Fixes

* Electricity price sensor fails if no Dynamic Pulse subscription exists ([3db2872](https://github.com/BirknerAlex/hacs_1komma5grad/commit/3db28728dcf1c72067dd6b312743e06806df1fbb))
* Fix error when price data not existing ([c2b7a0d](https://github.com/BirknerAlex/hacs_1komma5grad/commit/c2b7a0d7224beae684c17759e9542b2ab626a6f9))

### 🚀 Features

* Added energy sensor to track kW/h for certain sensors ([c8e353c](https://github.com/BirknerAlex/hacs_1komma5grad/commit/c8e353ccf79549ffbb6fe5254e2319a164a19755))
* Migrate battery power sensors to 2 separate sensors for in and out ([8d0c077](https://github.com/BirknerAlex/hacs_1komma5grad/commit/8d0c077c91fa8cd69ea319d20ddfcba0b1f88e5f))

## [1.2.0-dev.2](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.2.0-dev.1...v1.2.0-dev.2) (2025-05-04)

### 🛠️ Fixes

* Fix error when price data not existing ([2066a94](https://github.com/BirknerAlex/hacs_1komma5grad/commit/2066a94b96140461b6a76ecf88a75c63b37c1bdd))

## [1.2.0-dev.1](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.1.0...v1.2.0-dev.1) (2025-04-28)

### 🚀 Features

* Added energy sensor to track kW/h for certain sensors ([b33d93b](https://github.com/BirknerAlex/hacs_1komma5grad/commit/b33d93b1475149e6a87e826c7ab34bf77a521951))
* Migrate battery power sensors to 2 separate sensors for in and out ([202f783](https://github.com/BirknerAlex/hacs_1komma5grad/commit/202f7836f80d5b18ff6e3377b3971c93b62fae8a))

### 🛠️ Fixes

* Electricity price sensor fails if no Dynamic Pulse subscription exists ([962981c](https://github.com/BirknerAlex/hacs_1komma5grad/commit/962981cea8fca788c8c31088da85bec1b4a13378))

## [1.1.0](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.4...v1.1.0) (2025-04-27)

### 🚀 Features

* Added Battery sensors for power and state of charge ([47840cb](https://github.com/BirknerAlex/hacs_1komma5grad/commit/47840cb7b76afaad7eac9f7d0672e5848c6eed57)), closes [#8](https://github.com/BirknerAlex/hacs_1komma5grad/issues/8)

### 🛠️ Fixes

* Fix price calculation by calculating it by myself instead of use API response ([fa62cfa](https://github.com/BirknerAlex/hacs_1komma5grad/commit/fa62cfafea54ac671a90ed479d6e6fadb9d15d9b)), closes [#7](https://github.com/BirknerAlex/hacs_1komma5grad/issues/7)

## [1.1.0-dev.1](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.5-dev.1...v1.1.0-dev.1) (2025-04-27)

### 🚀 Features

* Added Battery sensors for power and state of charge ([3aa8d68](https://github.com/BirknerAlex/hacs_1komma5grad/commit/3aa8d6874e25ed2d44089781ff522be503b554ec)), closes [#8](https://github.com/BirknerAlex/hacs_1komma5grad/issues/8)

## [1.0.5-dev.1](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.4...v1.0.5-dev.1) (2025-04-27)

### 🛠️ Fixes

* Fix price calculation by calculating it by myself instead of use API response ([5de8b88](https://github.com/BirknerAlex/hacs_1komma5grad/commit/5de8b88fbb1cbe25c6ae38cc612756b62b72aad2)), closes [#7](https://github.com/BirknerAlex/hacs_1komma5grad/issues/7)

## [1.0.4](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.3...v1.0.4) (2024-12-23)

### 🛠️ Fixes

* Handle missing refresh token properly ([5cb3533](https://github.com/BirknerAlex/hacs_1komma5grad/commit/5cb35337b0eccbe6fe3112d6ca703e9a8457579b))

## [1.0.4-dev.1](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.3...v1.0.4-dev.1) (2024-12-23)

### 🛠️ Fixes

* Handle missing refresh token properly ([5cb3533](https://github.com/BirknerAlex/hacs_1komma5grad/commit/5cb35337b0eccbe6fe3112d6ca703e9a8457579b))

## [1.0.3](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.2...v1.0.3) (2024-12-03)

### 🛠️ Fixes

* **pricing:** Add VAT to energy price sensor ([6c8453e](https://github.com/BirknerAlex/hacs_1komma5grad/commit/6c8453ea8491bf6e642f8a49b202290f4ca61a13))

## [1.0.3-dev.1](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.2...v1.0.3-dev.1) (2024-12-03)

### 🛠️ Fixes

* **pricing:** Add VAT to energy price sensor ([6c8453e](https://github.com/BirknerAlex/hacs_1komma5grad/commit/6c8453ea8491bf6e642f8a49b202290f4ca61a13))

## [1.0.2](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.1...v1.0.2) (2024-12-03)

### 🛠️ Fixes

* Handle expired token and refresh if needed ([012d865](https://github.com/BirknerAlex/hacs_1komma5grad/commit/012d8654b5fe56a438c8e3e55b5dfaf39f4e1aed))
* **ci:** Fetch tags for release ([aca374f](https://github.com/BirknerAlex/hacs_1komma5grad/commit/aca374f3cc906ae6cb36a81feafab4209e8927bd))
* **deps:** Remove deps since they are both already provided by homeassistant-core ([f49f744](https://github.com/BirknerAlex/hacs_1komma5grad/commit/f49f74467b3a61da61a8cd9911cdb90d3fa813d1))
* **integration:** Fix EMS switch missing unique_id property ([ce0e9d2](https://github.com/BirknerAlex/hacs_1komma5grad/commit/ce0e9d202086d291f0933532a780d6dc067b0160))
* **linting:** Fix linting issues and replace linter with ruff ([1b5edc5](https://github.com/BirknerAlex/hacs_1komma5grad/commit/1b5edc5b59e612ef9266eb1951825321c4582860))
* **repo:** Cleanup pycache files from git repository ([d2f1074](https://github.com/BirknerAlex/hacs_1komma5grad/commit/d2f10747792ffddce421ddbf93b4bfad9a9643e9))
* **repo:** Cleanup pycache files from git repository ([2076f31](https://github.com/BirknerAlex/hacs_1komma5grad/commit/2076f3153f0e47261dc105cd731bf9e1e291e4ea))

### 📔 Docs

* **readme:** Added Installation button ([f40df7d](https://github.com/BirknerAlex/hacs_1komma5grad/commit/f40df7db9785600b14123e91cf154e0bb0782875))

## [1.0.2-dev.6](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.2-dev.5...v1.0.2-dev.6) (2024-12-03)

### 🛠️ Fixes

* **ci:** Fetch tags for release ([aca374f](https://github.com/BirknerAlex/hacs_1komma5grad/commit/aca374f3cc906ae6cb36a81feafab4209e8927bd))

## [1.0.2](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.1...v1.0.2) (2024-12-03)

### 🛠️ Fixes

* Handle expired token and refresh if needed ([012d865](https://github.com/BirknerAlex/hacs_1komma5grad/commit/012d8654b5fe56a438c8e3e55b5dfaf39f4e1aed))
* **deps:** Remove deps since they are both already provided by homeassistant-core ([f49f744](https://github.com/BirknerAlex/hacs_1komma5grad/commit/f49f74467b3a61da61a8cd9911cdb90d3fa813d1))
* **integration:** Fix EMS switch missing unique_id property ([ce0e9d2](https://github.com/BirknerAlex/hacs_1komma5grad/commit/ce0e9d202086d291f0933532a780d6dc067b0160))
* **linting:** Fix linting issues and replace linter with ruff ([1b5edc5](https://github.com/BirknerAlex/hacs_1komma5grad/commit/1b5edc5b59e612ef9266eb1951825321c4582860))
* **repo:** Cleanup pycache files from git repository ([d2f1074](https://github.com/BirknerAlex/hacs_1komma5grad/commit/d2f10747792ffddce421ddbf93b4bfad9a9643e9))
* **repo:** Cleanup pycache files from git repository ([2076f31](https://github.com/BirknerAlex/hacs_1komma5grad/commit/2076f3153f0e47261dc105cd731bf9e1e291e4ea))

### 📔 Docs

* **readme:** Added Installation button ([f40df7d](https://github.com/BirknerAlex/hacs_1komma5grad/commit/f40df7db9785600b14123e91cf154e0bb0782875))

## [1.0.2-dev.5](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.2-dev.4...v1.0.2-dev.5) (2024-12-03)

### 🛠️ Fixes

* **deps:** Remove deps since they are both already provided by homeassistant-core ([f49f744](https://github.com/BirknerAlex/hacs_1komma5grad/commit/f49f74467b3a61da61a8cd9911cdb90d3fa813d1))

## [1.0.2-dev.4](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.2-dev.3...v1.0.2-dev.4) (2024-11-26)

### 🛠️ Fixes

* Handle expired token and refresh if needed ([012d865](https://github.com/BirknerAlex/hacs_1komma5grad/commit/012d8654b5fe56a438c8e3e55b5dfaf39f4e1aed))

## [1.0.2-dev.3](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.2-dev.2...v1.0.2-dev.3) (2024-11-19)

### 🛠️ Fixes

* **repo:** Cleanup pycache files from git repository ([d2f1074](https://github.com/BirknerAlex/hacs_1komma5grad/commit/d2f10747792ffddce421ddbf93b4bfad9a9643e9))

## [1.0.2-dev.2](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.2-dev.1...v1.0.2-dev.2) (2024-11-19)

### 🛠️ Fixes

* **repo:** Cleanup pycache files from git repository ([2076f31](https://github.com/BirknerAlex/hacs_1komma5grad/commit/2076f3153f0e47261dc105cd731bf9e1e291e4ea))

### 📔 Docs

* **readme:** Added Installation button ([f40df7d](https://github.com/BirknerAlex/hacs_1komma5grad/commit/f40df7db9785600b14123e91cf154e0bb0782875))

## [1.0.2-dev.1](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.1...v1.0.2-dev.1) (2024-11-19)

### 🛠️ Fixes

* **integration:** Fix EMS switch missing unique_id property ([ce0e9d2](https://github.com/BirknerAlex/hacs_1komma5grad/commit/ce0e9d202086d291f0933532a780d6dc067b0160))
* **linting:** Fix linting issues and replace linter with ruff ([1b5edc5](https://github.com/BirknerAlex/hacs_1komma5grad/commit/1b5edc5b59e612ef9266eb1951825321c4582860))

## [1.0.1](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.0...v1.0.1) (2024-11-19)

### 🛠️ Fixes

* **ci:** Update release configuration ([65efea7](https://github.com/BirknerAlex/hacs_1komma5grad/commit/65efea7382736ea80a3f8331086ffcc2345a63bf))

## [1.0.0-dev.2](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.0-dev.1...v1.0.0-dev.2) (2024-11-19)

### 🛠️ Fixes

* **ci:** Update release configuration ([7a689e0](https://github.com/BirknerAlex/hacs_1komma5grad/commit/7a689e0dcb67f3a3188a8fdc41fe4c1ffcc7fb97))

## [1.0.0-dev.1](https://github.com/BirknerAlex/hacs_1komma5grad/compare/...v1.0.0-dev.1) (2024-11-19)

### 🛠️ Fixes

* **ci:** Update CI configuration for dev release ([1e63b54](https://github.com/BirknerAlex/hacs_1komma5grad/commit/1e63b54ac06884f0411cc5f3844a89c0c9f00144))

### 🚀 Features

* **integration:** Initial Release ([fbee574](https://github.com/BirknerAlex/hacs_1komma5grad/commit/fbee5743ae4995bb2689d4c114f9d2a40c1df9e3))

## [1.0.0](https://github.com/BirknerAlex/hacs_1komma5grad/compare/...v1.0.0) (2024-11-19)

### 🚀 Features

* **integration:** Initial Release ([fbee574](https://github.com/BirknerAlex/hacs_1komma5grad/commit/fbee5743ae4995bb2689d4c114f9d2a40c1df9e3))

## [1.0.1](https://github.com/BirknerAlex/hacs_1komma5grad/compare/v1.0.0...v1.0.1) (2024-11-19)

### 🛠️ Fixes

* **ci:** Fixing CI configuration ([b7acfb2](https://github.com/BirknerAlex/hacs_1komma5grad/commit/b7acfb27b2c36e2c7daf4aeee4994b44361ce6ca))
