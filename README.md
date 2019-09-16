# golem-smart-contracts-interface
Python module that interfaces communication with BlockChain. Common for Golem and Concent.

[![CircleCI](https://circleci.com/gh/golemfactory/golem-smart-contracts-interface.svg?style=svg)](https://circleci.com/gh/golemfactory/golem-smart-contracts-interface)

### Main assumptions
- Gas limits are calculated manually and assume the most expensive scenario. Which means the transaction will never run out of gas regardless of the current blockchain state.
- While sending the transaction the ETH needed for gas and the transaction itself is locked until the transaction is confirmed required number of times.
- Background operations are run in their own separate thread. Any callbacks are invoked from this thread. That means that the caller has to take care of the thread safety on their own. E.g. if the caller uses asyncio they should make the callback schedule the real work to run in the event loop.
- Transactions are stored in the persistent `TransactionStorage` until they are mined and confirmed required number of times. During that period they will be rebroadcasted when necessary. Overriding the transaction is not supported (e.g. bumping the gas price).
