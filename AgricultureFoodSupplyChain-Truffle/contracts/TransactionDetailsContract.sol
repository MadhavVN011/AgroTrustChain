pragma solidity >=0.4.22 <0.9.0;
    contract TransactionDetailsContract {
    string public agricultureBoardID;
	string public buyerID;
	string public farmerID;
	string public productID;
	int public price;
	int public qty;
	
    
    function perform_transactions(string memory _agricultureBoardID, string memory _buyerID, string memory _farmerID, string memory _productID, int _price, int _qty) public{
       agricultureBoardID = _agricultureBoardID;
		buyerID = _buyerID;
		farmerID = _farmerID;
		productID = _productID;
		price = _price;
		qty = _qty;
		
    }

    // Tip of the application's SHA-256 hash chain (see HashChain.py). The app
    // anchors it here every time it seals blocks, so a database chain that was
    // rewritten and re-hashed no longer matches what is recorded on Ethereum.
    address public owner = msg.sender;
    bytes32 public chainHead;
    uint public chainLength;

    event ChainAnchored(uint chainLength, bytes32 chainHead);

    function anchorChain(bytes32 _chainHead, uint _chainLength) public {
        require(msg.sender == owner, "Only the deployer can anchor the chain");
        chainHead = _chainHead;
        chainLength = _chainLength;
        emit ChainAnchored(_chainLength, _chainHead);
    }
        
}
