# Project Iskander — Foundry Makefile
# Requires: forge, cast (Foundry toolchain) and a running Anvil node for local deploys.
# Install Foundry: curl -L https://foundry.paradigm.xyz | bash && foundryup

-include .env

.PHONY: install build test deploy-local deploy-gnosis verify-gnosis clean snapshot

## Install OpenZeppelin as a Foundry lib dependency
install:
	forge install OpenZeppelin/openzeppelin-contracts --no-git

## Compile contracts
build:
	forge build

## Run test suite
test:
	forge test -vvv

## Run tests with gas snapshot
snapshot:
	forge snapshot

## Deploy to local Anvil (requires .env with DEPLOYER_PRIVATE_KEY etc.)
deploy-local:
	forge script script/Deploy.s.sol \
		--rpc-url http://localhost:8545 \
		--broadcast \
		--private-key $(DEPLOYER_PRIVATE_KEY) \
		-vvvv

## Deploy to Gnosis Chain (requires .env with DEPLOYER_PRIVATE_KEY, GNOSIS_RPC_URL)
deploy-gnosis:
	forge script script/Deploy.s.sol \
		--rpc-url $(GNOSIS_RPC_URL) \
		--broadcast \
		--verify \
		--private-key $(DEPLOYER_PRIVATE_KEY) \
		-vvvv

## Verify contracts on Gnosisscan after deployment
verify-gnosis:
	@echo "Verify each contract address from script/deployment.json on Gnosisscan."
	@echo "Use: forge verify-contract <ADDRESS> <CONTRACT> --chain gnosis"

## Clean build artefacts
clean:
	forge clean
