ADDRESS = '0x924442a66cfd812308791872c4b242440c108e19'
ABI = '[{"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"golemFactory","outputs":[{"name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_master","type":"address"}],"name":"setMigrationMaster","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_value","type":"uint256"}],"name":"migrate","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":false,"inputs":[],"name":"finalize","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":false,"inputs":[],"name":"refund","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"migrationMaster","outputs":[{"name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"tokenCreationCap","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_agent","type":"address"}],"name":"setMigrationAgent","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"totalTokens","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"migrationAgent","outputs":[{"name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"fundingEndBlock","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"totalMigrated","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"tokenCreationMin","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"funding","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"tokenCreationRate","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"fundingStartBlock","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[],"name":"create","outputs":[],"payable":true,"stateMutability":"payable","type":"function"},{"inputs":[{"name":"_golemFactory","type":"address"},{"name":"_migrationMaster","type":"address"},{"name":"_fundingStartBlock","type":"uint256"},{"name":"_fundingEndBlock","type":"uint256"}],"payable":false,"stateMutability":"nonpayable","type":"constructor"},{"anonymous":false,"inputs":[{"indexed":true,"name":"_from","type":"address"},{"indexed":true,"name":"_to","type":"address"},{"indexed":false,"name":"_value","type":"uint256"}],"name":"Transfer","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"_from","type":"address"},{"indexed":true,"name":"_to","type":"address"},{"indexed":false,"name":"_value","type":"uint256"}],"name":"Migrate","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"_from","type":"address"},{"indexed":false,"name":"_value","type":"uint256"}],"name":"Refund","type":"event"}]'  # noqa
BIN = '60606040526001600260006101000a81548160ff021916908315150217905550341561002a57600080fd5b6040516080806115468339810160405280805190602001909190805190602001909190805190602001909190805190602001909190505060008473ffffffffffffffffffffffffffffffffffffffff16141561008557600080fd5b60008373ffffffffffffffffffffffffffffffffffffffff1614156100a957600080fd5b43821115156100b757600080fd5b81811115156100c557600080fd5b836100ce6101f3565b808273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001915050604051809103906000f080151561011a57600080fd5b600460006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555082600360006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555083600260016101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff160217905550816000819055508060018190555050505050610202565b604051606c806114da83390190565b6112c9806102116000396000f300606060405260043610610133576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff16806306fdde031461013857806316222950146101c657806318160ddd1461021b57806326316e5814610244578063313ce5671461027d578063454b0608146102ac5780634bb278f3146102cf578063590e1ae3146102e4578063676d2e62146102f95780636f7920fd1461034e57806370a082311461037757806375e2ff65146103c45780637e1c0c09146103fd5780638328dbcd1461042657806391b43d131461047b57806395a0f5eb146104a457806395d89b41146104cd578063a9059cbb1461055b578063c039daf6146105b5578063cb4c86b7146105de578063cf8d652c1461060b578063d648a64714610634578063efc81a8c1461065d575b600080fd5b341561014357600080fd5b61014b610667565b6040518080602001828103825283818151815260200191508051906020019080838360005b8381101561018b578082015181840152602081019050610170565b50505050905090810190601f1680156101b85780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b34156101d157600080fd5b6101d96106a0565b604051808273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b341561022657600080fd5b61022e6106c6565b6040518082815260200191505060405180910390f35b341561024f57600080fd5b61027b600480803573ffffffffffffffffffffffffffffffffffffffff169060200190919050506106d0565b005b341561028857600080fd5b610290610794565b604051808260ff1660ff16815260200191505060405180910390f35b34156102b757600080fd5b6102cd6004808035906020019091905050610799565b005b34156102da57600080fd5b6102e2610a22565b005b34156102ef57600080fd5b6102f7610c28565b005b341561030457600080fd5b61030c610dbe565b604051808273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b341561035957600080fd5b610361610de4565b6040518082815260200191505060405180910390f35b341561038257600080fd5b6103ae600480803573ffffffffffffffffffffffffffffffffffffffff16906020019091905050610df7565b6040518082815260200191505060405180910390f35b34156103cf57600080fd5b6103fb600480803573ffffffffffffffffffffffffffffffffffffffff16906020019091905050610e40565b005b341561040857600080fd5b610410610f41565b6040518082815260200191505060405180910390f35b341561043157600080fd5b610439610f47565b604051808273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b341561048657600080fd5b61048e610f6d565b6040518082815260200191505060405180910390f35b34156104af57600080fd5b6104b7610f73565b6040518082815260200191505060405180910390f35b34156104d857600080fd5b6104e0610f79565b6040518080602001828103825283818151815260200191508051906020019080838360005b83811015610520578082015181840152602081019050610505565b50505050905090810190601f16801561054d5780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b341561056657600080fd5b61059b600480803573ffffffffffffffffffffffffffffffffffffffff16906020019091908035906020019091905050610fb2565b604051808215151515815260200191505060405180910390f35b34156105c057600080fd5b6105c8611136565b6040518082815260200191505060405180910390f35b34156105e957600080fd5b6105f1611148565b604051808215151515815260200191505060405180910390f35b341561061657600080fd5b61061e61115b565b6040518082815260200191505060405180910390f35b341561063f57600080fd5b610647611164565b6040518082815260200191505060405180910390f35b61066561116a565b005b6040805190810160405280601881526020017f5465737420476f6c656d204e6574776f726b20546f6b656e000000000000000081525081565b600260019054906101000a900473ffffffffffffffffffffffffffffffffffffffff1681565b6000600554905090565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff1614151561072c57600080fd5b60008173ffffffffffffffffffffffffffffffffffffffff16141561075057600080fd5b80600360006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555050565b601281565b600260009054906101000a900460ff16156107b357600080fd5b6000600760009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614156107f957600080fd5b600081141561080757600080fd5b600660003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205481111561085357600080fd5b80600660003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600082825403925050819055508060056000828254039250508190555080600860008282540192505081905550600760009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16637a3130e333836040518363ffffffff167c0100000000000000000000000000000000000000000000000000000000028152600401808373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200182815260200192505050600060405180830381600087803b151561098457600080fd5b6102c65a03f1151561099557600080fd5b505050600760009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff167f18df02dcc52b9c494f391df09661519c0069bd8540141946280399408205ca1a836040518082815260200191505060405180910390a350565b600080600260009054906101000a900460ff161515610a4057600080fd5b60015443111580610a6057506402540be40066354a6ba7a1800002600554105b8015610a7c57506402540be4006701235290c795000002600554105b15610a8657600080fd5b6000600260006101000a81548160ff02191690831515021790555060129150816064038260055402811515610ab757fe5b049050806005600082825401925050819055508060066000600460009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008282540192505081905550600460009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1660007fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a3600260019054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff166108fc3073ffffffffffffffffffffffffffffffffffffffff16319081150290604051600060405180830381858888f193505050501515610c2457600080fd5b5050565b600080600260009054906101000a900460ff161515610c4657600080fd5b60015443111515610c5657600080fd5b6402540be40066354a6ba7a1800002600554101515610c7457600080fd5b600660003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205491506000821415610cc457600080fd5b6000600660003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002081905550816005600082825403925050819055506402540be40082811515610d2957fe5b0490503373ffffffffffffffffffffffffffffffffffffffff167fbb28353e4598c3b9199101a66e0989549b659a59a54d2c27fbb183f1932c8e6d826040518082815260200191505060405180910390a23373ffffffffffffffffffffffffffffffffffffffff166108fc829081150290604051600060405180830381858888f193505050501515610dba57600080fd5b5050565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1681565b6402540be4006701235290c79500000281565b6000600660008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020549050919050565b600260009054906101000a900460ff1615610e5a57600080fd5b6000600760009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16141515610ea157600080fd5b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff16141515610efd57600080fd5b80600760006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555050565b60055481565b600760009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1681565b60015481565b60085481565b6040805190810160405280600481526020017f74474e540000000000000000000000000000000000000000000000000000000081525081565b600080600260009054906101000a900460ff1615610fcf57600080fd5b600660003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205490508281101580156110215750600083115b1561112a57828103905080600660003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000208190555082600660008673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600082825401925050819055508373ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef856040518082815260200191505060405180910390a36001915061112f565b600091505b5092915050565b6402540be40066354a6ba7a180000281565b600260009054906101000a900460ff1681565b6402540be40081565b60005481565b6000600260009054906101000a900460ff16151561118757600080fd5b60005443101561119657600080fd5b6001544311156111a557600080fd5b60003414156111b357600080fd5b6402540be4006005546402540be4006701235290c795000002038115156111d657fe5b043411156111e357600080fd5b6402540be400340290508060056000828254019250508190555080600660003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600082825401925050819055503373ffffffffffffffffffffffffffffffffffffffff1660007fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a3505600a165627a7a7230582018bd05fe31182b9e9d2bc3d90bae4965612b85c94e246757fcb71c889cc548ec002960606040523415600e57600080fd5b604051602080606c833981016040528080519060200190919050505060358060376000396000f3006060604052600080fd00a165627a7a7230582035e240e36b16fd2fb3adf4c27ed97cfed046edf5781fec566ebe3d62e7e00bc20029'  # noqa
