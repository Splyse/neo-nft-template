# Neo Non-Fungible Token Template


### What is a non-fungible token?
A non-fungible token (NFT) can be thought of like a property deed - each one is unique and carries some non-mutable information (e.g. the physical address of the property) although other information, such as the owner of the property can be changed. 
An NFT smart contract is useful to track ownership of real-world items, as well as in online gaming, allowing users to posess unique characters or items of a limited supply, that can be transferred between users without requiring the permission of the game owner.

The NFT proposal standard for the Neo Smart Economy is currently in development. This is a draft template example in Python showing how such a smart contract might be written. There is some overlap between NEP-5 (fungible) token functionality to make adoption easier by API writers.

### Smart Contract Operations
The operations of the NFT template contract are:  

  * **allowance**(token_id): returns approved third-party spender of a token
  * **approve**(owner, spender, token_id, revoke): approve third party to spend a token
  * **balanceOf**(owner): returns owner's current total tokens owned
  * **mintToken**(owner, properties, URI, extra_arg): create a new NFT token
  * **modifyURI**(token_id, URI): modify a token's URI
  * **name**(): returns name of token
  * **ownerOf**(token_id): returns owner of a token
  * **properties**(token_id): returns a token's read-only data
  * **supportedStandards**(): returns a list of supported standards {"NEP-10"}
  * **symbol**(): returns token symbol
  * **token**(token_id): returns a dictionary where token, property, and uri keys map to their corresponding token's data
  * **tokensOfOwner**(owner, start_index): returns a dictionary that contains less than or equal to ten of the tokens owned by the specified address starting at the `start_index` and all their data.
  * **totalSupply**(): Returns the total token supply deployed in the system
  * **transfer**(to, token_id, extra_arg): transfers a token
  * **transferFrom**(spender, from, to, token_id): transfers a token by authorized spender
  * **uri**(token_id): returns a token's URI
